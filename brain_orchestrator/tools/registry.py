"""Реестр инструментов агентов."""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Dict

from brain_orchestrator.tools.base import BaseTool, ToolSpec


class ToolRegistry:
    """Хранит и предоставляет инструменты по capability."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}
        self._auto_register()

    def register(self, tool: BaseTool) -> None:
        """Добавляет инструмент в реестр."""

        spec: ToolSpec = tool.spec
        if spec.capability in self._tools:
            raise ValueError(f"Capability уже зарегистрирован: {spec.capability}")
        self._tools[spec.capability] = tool

    def resolve(self, capability: str) -> BaseTool:
        """Возвращает инструмент по capability."""

        try:
            return self._tools[capability]
        except KeyError as exc:
            raise KeyError(f"Не найден инструмент для capability={capability}") from exc

    def _auto_register(self) -> None:
        """Импортирует модули tools.* и вызывает register_tools, если доступно."""

        package = importlib.import_module("tools")
        package_path = package.__path__  # type: ignore[attr-defined]
        prefix = package.__name__ + "."
        for module_info in pkgutil.iter_modules(package_path, prefix=prefix):
            module = importlib.import_module(module_info.name)
            register = getattr(module, "register_tools", None)
            if callable(register):
                register(self)
