"""Заглушка для будущих алертов в Telegram (не активна)."""

from __future__ import annotations

from brain_orchestrator.tools.base import ToolContext, ToolSpec


class TelegramAlertTool:
    """Неактивная заглушка: возвращает предупреждение о запрете Telegram."""

    spec = ToolSpec(
        capability="alert_telegram",
        agent="monitor",
        read_only=True,
        safety_tags=("disabled",),
        cost_hint_ms=1,
    )

    def execute(self, context: ToolContext, **kwargs) -> str:
        return "Telegram алерты запрещены: см. Инструкция Codex."


def register_tools(registry) -> None:
    registry.register(TelegramAlertTool())
