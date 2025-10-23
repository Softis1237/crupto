"""Базовые классы инструментов агентов."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class ToolSpec:
    """Описание инструмента для регистрации в оркестраторе."""

    capability: str
    agent: str
    read_only: bool
    safety_tags: tuple[str, ...]
    cost_hint_ms: int


@dataclass(slots=True)
class ToolContext:
    """Контекст выполнения инструмента."""

    mode: str
    symbol: str
    timeframe: str | None = None
    last_price: float | None = None  # Последняя известная цена инструмента


class BaseTool(Protocol):
    """Интерфейс, который должны реализовывать все инструменты."""

    spec: ToolSpec

    def execute(self, context: ToolContext, **kwargs: Any) -> Any:
        """Выполняет инструмент и возвращает результат."""
