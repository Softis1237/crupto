"""Риск-менеджер: расчёт объёмов и адаптивных лимитов."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from prod_core.persist import PersistDAO

from prod_core.strategies.base import StrategySignal


@dataclass(slots=True)
class RiskSettings:
    """Жёсткие лимиты согласно ТЗ."""

    per_trade_r_pct_base: float = 0.8
    risk_bonus_threshold_pct: float = 0.5
    risk_bonus_add: float = 0.3
    max_per_trade_r_pct: float = 1.1
    max_daily_loss_pct: float = 1.8
    kill_switch_drawdown_72h: float = 3.5
    leverage_cap: float = 3.0
    max_portfolio_r_pct: float = 1.5
    losing_streak_lookback: int = 5
    volatility_threshold: float = 0.04
    volatility_risk_step: float = 0.2
    min_r_pct_floor: float = 0.25


@dataclass(slots=True)
class RiskState:
    """Текущее состояние риска портфеля."""

    equity: float
    daily_pnl_pct: float
    trailing_drawdown_72h_pct: float
    losing_streak: int
    realized_volatility: float
    portfolio_risk_pct: float
    gross_exposure_pct: float = 0.0
    net_exposure_pct: float = 0.0


class RiskEngine:
    """Вычисляет объёмы сделок и контролирует риск."""

    CONTRACT_VALUE: Final[float] = 1.0  # базовое значение контракта, переопределяется конфигом

    def __init__(self, settings: RiskSettings | None = None, dao: PersistDAO | None = None) -> None:
        self.settings = settings or RiskSettings()
        self.dao = dao

    def risk_budget_pct(self, state: RiskState) -> float:
        """Рассчитывает доступный риск на сделку с учётом динамических ограничений."""

        settings = self.settings
        if state.daily_pnl_pct <= -settings.max_daily_loss_pct:
            return 0.0
        if state.trailing_drawdown_72h_pct <= -settings.kill_switch_drawdown_72h:
            return 0.0

        risk_pct = settings.per_trade_r_pct_base
        if state.daily_pnl_pct >= settings.risk_bonus_threshold_pct:
            risk_pct = min(risk_pct + settings.risk_bonus_add, settings.max_per_trade_r_pct)

        risk_pct = self._apply_dynamic_reduction(risk_pct, state)

        available_vs_portfolio = max(0.0, settings.max_portfolio_r_pct - state.portfolio_risk_pct)
        return max(0.0, min(risk_pct, available_vs_portfolio))

    def _apply_dynamic_reduction(self, risk_pct: float, state: RiskState) -> float:
        """Снижает риск при просадке или высокой волатильности."""

        settings = self.settings
        adjusted = risk_pct

        if state.losing_streak > 1:
            reduction_factor = 1 - min(0.5, 0.1 * (state.losing_streak - 1))
            adjusted *= reduction_factor

        if state.realized_volatility > settings.volatility_threshold:
            excess = state.realized_volatility - settings.volatility_threshold
            vol_reduction = 1 - min(0.5, excess / settings.volatility_threshold * settings.volatility_risk_step)
            adjusted *= max(0.5, vol_reduction)

        return max(settings.min_r_pct_floor, adjusted)

    def size_position(
        self,
        signal: StrategySignal,
        entry_price: float,
        state: RiskState,
        atr: float | None = None,
    ) -> float:
        """Возвращает размер позиции в контрактах, ограниченный риском и плечом."""

        risk_pct = self.risk_budget_pct(state)
        if risk_pct <= 0:
            return 0.0

        stop_distance = self._stop_distance(signal, entry_price, atr)
        if stop_distance <= 0:
            return 0.0

        equity = state.equity
        if equity <= 0 and self.dao is not None:
            snapshot = self.dao.fetch_equity_last()
            if snapshot:
                equity = float(snapshot.get("equity_usd", 0.0))
        if equity <= 0:
            return 0.0

        capital_at_risk = equity * (risk_pct / 100)
        contracts = capital_at_risk / stop_distance

        # Ограничение плеча
        notional = contracts * entry_price * self.CONTRACT_VALUE
        leverage = notional / max(equity, 1e-9)
        if leverage > self.settings.leverage_cap:
            contracts *= self.settings.leverage_cap / leverage

        return max(0.0, contracts)

    def _stop_distance(self, signal: StrategySignal, entry_price: float, atr: float | None) -> float:
        """Оценивает расстояние до стоп-лосса для расчёта риска."""

        if signal.stop_loss is not None:
            return abs(entry_price - signal.stop_loss)
        if atr is not None and atr > 0:
            return atr
        # Последний рубеж: фиксированный процент от цены
        return entry_price * 0.01
