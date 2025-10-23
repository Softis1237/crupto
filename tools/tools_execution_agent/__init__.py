"""Регистрация инструментов ExecutionAgent."""

from importlib import import_module
from typing import Sequence

MODULES: Sequence[str] = (
    "tools.tools_execution_agent.liquidity_check",
    "tools.tools_execution_agent.slippage_estimator",
    "tools.tools_execution_agent.order_placer_ccxt",
)


def register_tools(registry) -> None:
    for module_name in MODULES:
        module = import_module(module_name)
        if hasattr(module, "register_tools"):
            module.register_tools(registry)
