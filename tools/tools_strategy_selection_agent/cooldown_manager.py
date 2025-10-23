"""Инструмент управления cooldown стратегий."""

from __future__ import annotations

from brain_orchestrator.tools.base import ToolContext, ToolSpec
from prod_core.strategies import TradingStrategy


class CooldownManagerTool:
    """Блокирует повторный запуск стратегии раньше срока."""

    spec = ToolSpec(
        capability="manage_cooldown",
        agent="strategy_selection",
        read_only=False,
        safety_tags=("deterministic",),
        cost_hint_ms=5,
    )

    def __init__(self, cooldown_bars: int = 3) -> None:
        self.cooldown_bars = cooldown_bars

    def execute(self, context: ToolContext, **kwargs) -> bool:
        strategy: TradingStrategy = kwargs["strategy"]
        cooldown_state: dict[str, dict[str, int]] = kwargs.setdefault("cooldown_state", {})
        state = cooldown_state.setdefault(strategy.name, {"remaining": 0})
        if state["remaining"] > 0:
            state["remaining"] -= 1
            return False
        state["remaining"] = self.cooldown_bars
        return True


def register_tools(registry) -> None:
    registry.register(CooldownManagerTool())
