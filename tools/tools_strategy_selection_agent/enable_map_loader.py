"""Инструмент загрузки enable_map.yaml."""

from __future__ import annotations

import yaml

from brain_orchestrator.tools.base import ToolContext, ToolSpec


class EnableMapLoaderTool:
    """Загружает карту включения стратегий по режимам."""

    spec = ToolSpec(
        capability="load_enable_map",
        agent="strategy_selection",
        read_only=True,
        safety_tags=("deterministic",),
        cost_hint_ms=5,
    )

    def __init__(self, path: str = "configs/enable_map.yaml") -> None:
        self.path = path

    def execute(self, context: ToolContext, **kwargs):
        with open(self.path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return {str(key).lower(): value for key, value in data.items()}


def register_tools(registry) -> None:
    registry.register(EnableMapLoaderTool())
