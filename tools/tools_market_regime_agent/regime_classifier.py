"""Инструмент классификации режима рынка."""

from __future__ import annotations

from brain_orchestrator.regimes import RegimeDetector
from brain_orchestrator.tools.base import ToolContext, ToolSpec


class RegimeClassifierTool:
    """Использует RegimeDetector для вычисления режима."""

    spec = ToolSpec(
        capability="classify_regime",
        agent="market_regime",
        read_only=True,
        safety_tags=("deterministic",),
        cost_hint_ms=10,
    )

    def __init__(self) -> None:
        self._detector = RegimeDetector()

    def execute(self, context: ToolContext, **kwargs):
        features = kwargs["features"]
        return self._detector.detect(features)


def register_tools(registry) -> None:
    registry.register(RegimeClassifierTool())
