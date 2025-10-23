"""Инструмент оценки сллипеджа."""

from __future__ import annotations

from brain_orchestrator.tools.base import ToolContext, ToolSpec
from prod_core.strategies import StrategyPlan


class SlippageEstimatorTool:
    """Оценивает ожидаемый сллипедж как функцию размера и риска."""

    spec = ToolSpec(
        capability="estimate_slippage",
        agent="execution",
        read_only=True,
        safety_tags=("deterministic",),
        cost_hint_ms=2,
    )

    def execute(self, context: ToolContext, **kwargs) -> float:
        plan: StrategyPlan = kwargs["plan"]
        base_slippage = 0.0005
        size_factor = min(3.0, abs(plan.size) / 1000)
        return base_slippage * (1 + size_factor)


def register_tools(registry) -> None:
    registry.register(SlippageEstimatorTool())
