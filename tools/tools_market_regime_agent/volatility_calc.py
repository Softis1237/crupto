"""Инструмент расчёта волатильности."""

from __future__ import annotations

from brain_orchestrator.tools.base import ToolContext, ToolSpec
from prod_core.indicators import TechnicalIndicators


class VolatilityCalcTool:
    """Возвращает последнее значение волатильности для оценки режима."""

    spec = ToolSpec(
        capability="calc_volatility",
        agent="market_regime",
        read_only=True,
        safety_tags=("deterministic",),
        cost_hint_ms=10,
    )

    def __init__(self) -> None:
        self._indicators = TechnicalIndicators()

    def execute(self, context: ToolContext, **kwargs) -> float:
        features = kwargs["features"]
        if "volatility" in features.columns:
            return float(features["volatility"].iloc[-1])
        candles = kwargs.get("candles")
        if candles is None:
            raise ValueError("Для вычисления волатильности нужны features или candles.")
        volatility = self._indicators.volatility(candles["close"], window=30)
        return float(volatility.iloc[-1])


def register_tools(registry) -> None:
    registry.register(VolatilityCalcTool())
