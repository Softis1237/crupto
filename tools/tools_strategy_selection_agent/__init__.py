"""Регистрация инструментов StrategySelectionAgent."""

from importlib import import_module
from typing import Sequence

MODULES: Sequence[str] = (
    "tools.tools_strategy_selection_agent.enable_map_loader",
    "tools.tools_strategy_selection_agent.strategy_scorer",
    "tools.tools_strategy_selection_agent.cooldown_manager",
)


def register_tools(registry) -> None:
    for module_name in MODULES:
        module = import_module(module_name)
        if hasattr(module, "register_tools"):
            module.register_tools(registry)
