"""Инструмент дополнительного масштабирования позиции."""

from __future__ import annotations

from brain_orchestrator.tools.base import ToolContext, ToolSpec
from prod_core.strategies import StrategySignal


class PositionSizerTool:
    """Масштабирует позицию на основе уверенности сигнала."""

    spec = ToolSpec(
        capability="plan_position",
        agent="risk_manager",
        read_only=False,
        safety_tags=("deterministic",),
        cost_hint_ms=3,
    )

    def execute(self, context: ToolContext, **kwargs) -> float:
        signal: StrategySignal = kwargs["signal"]
        atr = kwargs.get("atr") or 0.0
        confidence_multiplier = max(0.5, min(1.5, signal.confidence))
        atr_modifier = 1.0 if atr == 0 else max(0.7, min(1.2, 0.02 / max(atr, 1e-6)))
        return confidence_multiplier * atr_modifier


def register_tools(registry) -> None:
    registry.register(PositionSizerTool())
