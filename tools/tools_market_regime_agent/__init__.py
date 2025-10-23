"""Регистрация инструментов MarketRegimeAgent."""

from importlib import import_module
from typing import Sequence

MODULES: Sequence[str] = (
    "tools.tools_market_regime_agent.feature_loader",
    "tools.tools_market_regime_agent.volatility_calc",
    "tools.tools_market_regime_agent.trend_detector",
    "tools.tools_market_regime_agent.regime_classifier",
)


def register_tools(registry) -> None:
    for module_name in MODULES:
        module = import_module(module_name)
        if hasattr(module, "register_tools"):
            module.register_tools(registry)
