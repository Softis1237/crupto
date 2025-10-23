"""Инструмент планирования стопов и тейков."""

from __future__ import annotations

from brain_orchestrator.tools.base import ToolContext, ToolSpec
from prod_core.strategies import StrategySignal


class StopPlannerTool:
    """Добавляет стоп и тейк на основе ATR."""

    spec = ToolSpec(
        capability="plan_stops",
        agent="risk_manager",
        read_only=False,
        safety_tags=("deterministic",),
        cost_hint_ms=3,
    )

    def execute(self, context: ToolContext, **kwargs) -> StrategySignal:
        signal: StrategySignal = kwargs["signal"]
        atr = float(kwargs.get("atr") or 0.0)
        price = float(kwargs.get("price") or 0.0)
        if atr <= 0 or price <= 0:
            return signal
        delta = atr * 1.2
        if signal.side == "long":
            signal.stop_loss = price - delta
            signal.take_profit = price + delta * 2.5
        elif signal.side == "short":
            signal.stop_loss = price + delta
            signal.take_profit = price - delta * 2.5
        return signal


def register_tools(registry) -> None:
    registry.register(StopPlannerTool())
