"""Инструмент проверки ликвидности перед выставлением заявки."""

from __future__ import annotations

from brain_orchestrator.tools.base import ToolContext, ToolSpec
from prod_core.strategies import StrategyPlan


class LiquidityCheckTool:
    """Грубая эвристика ликвидности на основе размера позиции."""

    spec = ToolSpec(
        capability="check_liquidity",
        agent="execution",
        read_only=True,
        safety_tags=("deterministic",),
        cost_hint_ms=2,
    )

    def __init__(self, max_contracts: float = 10_000.0) -> None:
        self.max_contracts = max_contracts

    def execute(self, context: ToolContext, **kwargs) -> bool:
        plan: StrategyPlan = kwargs["plan"]
        return abs(plan.size) <= self.max_contracts


def register_tools(registry) -> None:
    registry.register(LiquidityCheckTool())
