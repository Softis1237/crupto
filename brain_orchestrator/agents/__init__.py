"""Регистрация агентов оркестратора."""

from .brain_agent import BrainAgent
from .market_regime_agent import MarketRegimeAgent
from .strategy_selection_agent import StrategySelectionAgent
from .risk_manager_agent import RiskManagerAgent
from .execution_agent import ExecutionAgent
from .research_agent import ResearchAgent
from .monitor_agent import MonitorAgent

__all__ = [
    "BrainAgent",
    "MarketRegimeAgent",
    "StrategySelectionAgent",
    "RiskManagerAgent",
    "ExecutionAgent",
    "ResearchAgent",
    "MonitorAgent",
]
