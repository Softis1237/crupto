"""Инструмент контроля drawdown и дневных лимитов."""

from __future__ import annotations

from brain_orchestrator.tools.base import ToolContext, ToolSpec
from prod_core.risk import RiskState


class DrawdownGuardTool:
    """Возвращает False, если достигнуты жёсткие лимиты риска."""

    spec = ToolSpec(
        capability="guard_drawdown",
        agent="risk_manager",
        read_only=True,
        safety_tags=("deterministic",),
        cost_hint_ms=2,
    )

    def __init__(self, max_daily_loss_pct: float = 1.8, kill_switch_drawdown_72h: float = 3.5) -> None:
        self.max_daily_loss_pct = max_daily_loss_pct
        self.kill_switch_drawdown_72h = kill_switch_drawdown_72h

    def execute(self, context: ToolContext, **kwargs) -> bool:
        state: RiskState = kwargs["state"]
        if state.daily_pnl_pct <= -self.max_daily_loss_pct:
            return False
        if state.trailing_drawdown_72h_pct <= -self.kill_switch_drawdown_72h:
            return False
        return True


def register_tools(registry) -> None:
    registry.register(DrawdownGuardTool())
