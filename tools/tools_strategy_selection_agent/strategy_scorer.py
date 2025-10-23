"""Инструмент скоринга стратегий."""

from __future__ import annotations

import pandas as pd

from brain_orchestrator.tools.base import ToolContext, ToolSpec
from prod_core.strategies import TradingStrategy


class StrategyScorerTool:
    """Простая эвристика отбора стратегий."""

    spec = ToolSpec(
        capability="score_strategy",
        agent="strategy_selection",
        read_only=True,
        safety_tags=("deterministic",),
        cost_hint_ms=10,
    )

    def execute(self, context: ToolContext, **kwargs) -> float:
        strategy: TradingStrategy = kwargs["strategy"]
        features: pd.DataFrame = kwargs["features"]
        returns = float(features["return_lag"].iloc[-1])
        volatility = float(features["volatility"].iloc[-1])
        bias = 1 if returns >= 0 else -1
        score = bias * returns - volatility * 0.5
        # Стратегии mean-reversion имеют обратный знак
        if "range" in strategy.name:
            score *= -1
        return score


def register_tools(registry) -> None:
    registry.register(StrategyScorerTool())
