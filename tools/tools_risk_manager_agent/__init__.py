"""Регистрация инструментов RiskManagerAgent."""

from importlib import import_module
from typing import Sequence

MODULES: Sequence[str] = (
    "tools.tools_risk_manager_agent.position_sizer",
    "tools.tools_risk_manager_agent.stop_planner",
    "tools.tools_risk_manager_agent.dd_guard",
)


def register_tools(registry) -> None:
    for module_name in MODULES:
        module = import_module(module_name)
        if hasattr(module, "register_tools"):
            module.register_tools(registry)
