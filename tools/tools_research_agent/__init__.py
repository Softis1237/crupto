"""Регистрация инструментов ResearchAgent."""

from importlib import import_module
from typing import Sequence

MODULES: Sequence[str] = (
    "tools.tools_research_agent.generate_candidate",
    "tools.tools_research_agent.backtest_runner",
    "tools.tools_research_agent.walkforward_runner",
    "tools.tools_research_agent.montecarlo_runner",
)


def register_tools(registry) -> None:
    for module_name in MODULES:
        module = import_module(module_name)
        if hasattr(module, "register_tools"):
            module.register_tools(registry)
