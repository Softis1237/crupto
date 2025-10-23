"""Главный оркестратор после агентов."""

from __future__ import annotations

from typing import Sequence
import time

import pandas as pd

from brain_orchestrator.agents.execution_agent import ExecutionAgent
from brain_orchestrator.agents.market_regime_agent import MarketRegimeAgent
from brain_orchestrator.agents.monitor_agent import MonitorAgent
from brain_orchestrator.agents.risk_manager_agent import RiskManagerAgent
from brain_orchestrator.agents.strategy_selection_agent import StrategySelectionAgent
from brain_orchestrator.regimes import MarketRegime
from brain_orchestrator.tools import ToolRegistry
from brain_orchestrator.tools.base import ToolContext
from prod_core.exec.portfolio import PortfolioController
from prod_core.monitor.telemetry import TelemetryExporter
from prod_core.persist import LatencyPayload, PersistDAO
from prod_core.persist.shadow_logger import ShadowLogRecord, ShadowLogger
from prod_core.risk import RiskEngine
from prod_core.strategies import TradingStrategy
from prod_core.strategies.base import StrategySignal


class BrainOrchestrator:
    """Главный orchestrator для пайплайна."""

    def __init__(
        self,
        registry: ToolRegistry,
        telemetry: TelemetryExporter,
        strategies: Sequence[TradingStrategy],
        risk_engine: RiskEngine,
        dao: PersistDAO,
        portfolio: PortfolioController,
        challengers: Sequence[TradingStrategy] | None = None,
        shadow_logger: ShadowLogger | None = None,
    ) -> None:
        self.registry = registry
        self.telemetry = telemetry
        self.strategies = list(strategies)
        self.risk_engine = risk_engine
        self.dao = dao
        self.portfolio = portfolio

        self.market_agent = MarketRegimeAgent(registry, telemetry)
        self.strategy_agent = StrategySelectionAgent(registry)
        self.risk_agent = RiskManagerAgent(registry, risk_engine, portfolio=self.portfolio, dao=dao)
        self.execution_agent = ExecutionAgent(registry, portfolio=self.portfolio, dao=dao)
        self.monitor_agent = MonitorAgent(registry, telemetry, dao=dao)
        self.challengers: list[TradingStrategy] = list(challengers or [])
        self.shadow_logger = shadow_logger

    def run_cycle(
        self,
        candles: pd.DataFrame,
        state: dict[str, float],
        mode: str,
        symbol: str,
        timeframe: str,
    ) -> None:
        tool_context = ToolContext(mode=mode, symbol=symbol, timeframe=timeframe)

        start = time.perf_counter()
        features_map, regime = self.market_agent.run(tool_context, candles)
        self._observe_latency("market_regime", start)

        primary_features = features_map.get(symbol, {}).get(timeframe, pd.DataFrame())

        locked, reason = self._evaluate_daily_lock(state)
        self.telemetry.record_daily_lock(locked, reason)

        start = time.perf_counter()
        selected = self.strategy_agent.run(tool_context, self.strategies, regime, primary_features)
        self._observe_latency("strategy_selection", start)

        start = time.perf_counter()
        plans = self.risk_agent.run(tool_context, selected, candles, primary_features, regime, state)
        self._observe_latency("risk_manager", start)
        self.telemetry.record_portfolio_safe_mode(self.portfolio.safe_mode)

        start = time.perf_counter()
        executions = self.execution_agent.run(tool_context, plans)
        self._observe_latency("execution", start)

        start = time.perf_counter()
        self.monitor_agent.run(tool_context, primary_features, regime, executions)
        self._run_shadow(tool_context, candles, primary_features, regime)
        self._observe_latency("monitor", start)

    def _run_shadow(
        self,
        context: ToolContext,
        candles: pd.DataFrame,
        features: pd.DataFrame,
        regime: MarketRegime,
    ) -> None:
        if not self.challengers or not self.shadow_logger:
            return
        if candles.empty:
            return
        price = float(candles["close"].iloc[-1])
        for strategy in self.challengers:
            strategy_id = getattr(strategy, "shadow_id", strategy.name)
            signals = strategy.generate_signals(candles, features, regime)
            for signal in signals:
                record = ShadowLogRecord(
                    run_id=self.dao.run_id or "unknown",
                    strategy_id=strategy_id,
                    symbol=context.symbol,
                    timeframe=context.timeframe or "",
                    timestamp=signal.timestamp,
                    side=signal.side,
                    price=price,
                    confidence=signal.confidence,
                    expected_rr=self._estimate_expected_rr(signal, price),
                    metadata=signal.metadata,
                )
                self.shadow_logger.log(record)

    @staticmethod
    def _estimate_expected_rr(signal: StrategySignal, price: float) -> float:
        take_profit = signal.take_profit
        stop_loss = signal.stop_loss
        if take_profit is None or stop_loss is None:
            return 0.0
        if signal.side == "long":
            return (take_profit - price) - (price - stop_loss)
        if signal.side == "short":
            return (price - take_profit) - (stop_loss - price)
        return 0.0

    def _evaluate_daily_lock(self, state: dict[str, float]) -> tuple[bool, str]:
        limits = self.risk_engine.settings
        daily_pnl = float(state.get("daily_pnl_pct", 0.0))
        drawdown = float(state.get("drawdown_72h_pct", 0.0))
        if drawdown <= -limits.kill_switch_drawdown_72h:
            return True, f"kill_switch_dd72h={drawdown:.2f}%"
        if daily_pnl <= -limits.max_daily_loss_pct:
            return True, f"max_daily_loss={daily_pnl:.2f}%"
        return False, "limits_ok"

    def _observe_latency(self, stage: str, start_time: float) -> None:
        elapsed = time.perf_counter() - start_time
        self.telemetry.observe_stage_latency(stage, elapsed)
        self.dao.insert_latency(
            LatencyPayload(
                ts=int(time.time()),
                stage=stage,
                ms=elapsed * 1000,
                run_id=self.dao.run_id,
            )
        )
