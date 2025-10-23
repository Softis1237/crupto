"""Инструмент расчёта признаков для MarketRegimeAgent."""

from __future__ import annotations

from brain_orchestrator.tools.base import BaseTool, ToolContext, ToolSpec
from prod_core.data import FeatureEngineer


class FeatureLoaderTool:
    """Оборачивает FeatureEngineer для оркестратора."""

    spec = ToolSpec(
        capability="calc_features",
        agent="market_regime",
        read_only=True,
        safety_tags=("deterministic",),
        cost_hint_ms=20,
    )

    def __init__(self) -> None:
        self._engineer = FeatureEngineer()

    def execute(self, context: ToolContext, **kwargs):
        candles = kwargs["candles"]
        timeframe = context.timeframe or kwargs.get("timeframe") or "primary"

        if isinstance(candles, dict):
            return self._engineer.build_map(candles)

        symbol = context.symbol
        if not symbol:
            raise ValueError("Не задан символ для контекста признаков")

        candles_map = {
            symbol: {
                timeframe: candles,
            }
        }
        return self._engineer.build_map(candles_map)


def register_tools(registry) -> None:
    registry.register(FeatureLoaderTool())


