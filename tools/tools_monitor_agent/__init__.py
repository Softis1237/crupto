"""Регистрация инструментов MonitorAgent."""

from importlib import import_module
from typing import Sequence

MODULES: Sequence[str] = (
    "tools.tools_monitor_agent.prometheus_exporter",
    "tools.tools_monitor_agent.alert_telegram",
)


def register_tools(registry) -> None:
    for module_name in MODULES:
        module = import_module(module_name)
        if hasattr(module, "register_tools"):
            module.register_tools(registry)
