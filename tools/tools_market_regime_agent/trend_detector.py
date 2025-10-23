"""Инструмент определения направления тренда."""

from __future__ import annotations

from brain_orchestrator.tools.base import ToolContext, ToolSpec


class TrendDetectorTool:
    """Оценивает тренд по отношению EMA и ретёрнов."""

    spec = ToolSpec(
        capability="detect_trend",
        agent="market_regime",
        read_only=True,
        safety_tags=("deterministic",),
        cost_hint_ms=5,
    )

    def execute(self, context: ToolContext, **kwargs):
        features = kwargs["features"]
        ema_fast = float(features["ema_fast"].iloc[-1])
        ema_slow = float(features["ema_slow"].iloc[-1])
        return {"slope": ema_fast - ema_slow, "bias": 1 if ema_fast > ema_slow else -1}


def register_tools(registry) -> None:
    registry.register(TrendDetectorTool())
