"""Агент риск-менеджмента."""

from __future__ import annotations

from typing import Dict, List, Sequence

import pandas as pd

from brain_orchestrator.regimes import MarketRegime
from brain_orchestrator.tools import ToolRegistry
from brain_orchestrator.tools.base import ToolContext
from prod_core.exec.portfolio import PortfolioController
from prod_core.persist import PersistDAO
from prod_core.risk import RiskEngine, RiskState
from prod_core.strategies import StrategyPlan, TradingStrategy


class RiskManagerAgent:
    """Интегрирует RiskEngine с инструментами гейтов."""

    def __init__(
        self,
        registry: ToolRegistry,
        risk_engine: RiskEngine,
        portfolio: PortfolioController | None = None,
        dao: PersistDAO | None = None,
    ) -> None:
        self.registry = registry
        self.risk_engine = risk_engine
        self.dao = dao
        self.portfolio = portfolio or PortfolioController(dao=dao)

    def run(
        self,
        context: ToolContext,
        strategies: Sequence[TradingStrategy],
        candles: pd.DataFrame,
        features: pd.DataFrame,
        regime: MarketRegime,
        state: Dict[str, float],
    ) -> List[StrategyPlan]:
        """Возвращает планы сделок после всех риск-гейтов."""

        plans: List[StrategyPlan] = []
        guard_tool = self.registry.resolve("guard_drawdown")
        position_tool = self.registry.resolve("plan_position")
        stops_tool = self.registry.resolve("plan_stops")

        state = self._merge_state_with_persist(state)

        risk_state = RiskState(
            equity=state.get("equity", 0.0),
            daily_pnl_pct=state.get("daily_pnl_pct", 0.0),
            trailing_drawdown_72h_pct=state.get("drawdown_72h_pct", 0.0),
            losing_streak=int(state.get("losing_streak", 0)),
            realized_volatility=state.get("realized_volatility", 0.0),
            portfolio_risk_pct=state.get("portfolio_risk_pct", 0.0),
            gross_exposure_pct=state.get("gross_exposure_pct", 0.0),
            net_exposure_pct=state.get("net_exposure_pct", 0.0),
        )

        if not guard_tool.execute(context, state=risk_state):
            return plans

        if candles.empty or features.empty:
            return plans

        entry_price = float(candles["close"].iloc[-1])
        atr = float(features["atr"].iloc[-1]) if "atr" in features.columns else None
        self.portfolio.begin_cycle(
            current_risk_pct=risk_state.portfolio_risk_pct,
            gross_exposure_pct=risk_state.gross_exposure_pct,
            net_exposure_pct=risk_state.net_exposure_pct,
        )

        for strategy in strategies:
            signals = strategy.generate_signals(candles, features, regime)
            for signal in signals:
                enriched_signal = stops_tool.execute(context, signal=signal, atr=atr, price=entry_price)
                position_hint = position_tool.execute(context, signal=enriched_signal, atr=atr)

                risk_budget = self.risk_engine.risk_budget_pct(risk_state)
                if risk_budget <= 0:
                    continue

                contracts = self.risk_engine.size_position(
                    signal=enriched_signal,
                    entry_price=entry_price,
                    state=risk_state,
                    atr=atr,
                )
                contracts *= position_hint
                if contracts <= 0:
                    continue

                notional = abs(contracts) * entry_price * self.risk_engine.CONTRACT_VALUE
                equity = max(risk_state.equity, 1e-9)
                notional_pct = (notional / equity) * 100
                direction = 1 if enriched_signal.side == "long" else (-1 if enriched_signal.side == "short" else 0)
                if direction == 0:
                    continue

                if not self.portfolio.can_allocate(
                    context.symbol,
                    additional_r_pct=risk_budget,
                    notional_pct=notional_pct,
                    direction=direction,
                ):
                    continue

                lifetime = strategy._bar_duration() * 3  # приватный метод, но детерминированно
                plan = strategy.build_plan(
                    signal=enriched_signal,
                    atr=atr,
                    sizer=lambda _signal, _atr: contracts,
                    lifetime=lifetime,
                    risk_pct=risk_budget,
                )
                plans.append(plan)
                self.portfolio.register_position(
                    symbol=context.symbol,
                    risk_pct=risk_budget,
                    notional_pct=notional_pct,
                    direction=direction,
                    leverage=self.risk_engine.settings.leverage_cap,
                )
                risk_state.portfolio_risk_pct += risk_budget
                risk_state.gross_exposure_pct += abs(notional_pct)
                risk_state.net_exposure_pct += direction * notional_pct
        return plans

    def _merge_state_with_persist(self, state: Dict[str, float]) -> Dict[str, float]:
        """Обогащает состояние данными из DAO."""

        if not self.dao:
            return state

        snapshot = self.dao.fetch_equity_last()
        if snapshot:
            state["equity"] = float(snapshot.get("equity_usd", state.get("equity", 0.0)))
            state["gross_exposure_pct"] = float(snapshot.get("exposure_gross", state.get("gross_exposure_pct", 0.0)))
            state["net_exposure_pct"] = float(snapshot.get("exposure_net", state.get("net_exposure_pct", 0.0)))
            state["portfolio_risk_pct"] = float(snapshot.get("pnl_r_cum", state.get("portfolio_risk_pct", 0.0)))

        positions = self.dao.fetch_positions()
        equity = state.get("equity", 0.0)
        if positions and equity > 0:
            exposure_sum = sum(abs(pos.get("exposure_usd", 0.0)) for pos in positions)
            net_exposure = sum(pos.get("exposure_usd", 0.0) for pos in positions)
            state["portfolio_risk_pct"] = min(
                self.risk_engine.settings.max_portfolio_r_pct,
                (exposure_sum / state["equity"]) * 100,
            )
            state["gross_exposure_pct"] = (exposure_sum / equity) * 100
            state["net_exposure_pct"] = (net_exposure / equity) * 100
        return state


