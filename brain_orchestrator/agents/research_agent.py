"""Агент исследований стратегий (sandbox-only)."""

from __future__ import annotations

from typing import Any, Dict

from brain_orchestrator.tools import ToolRegistry
from brain_orchestrator.tools.base import ToolContext


class ResearchAgent:
    """Генерирует и валидирует новых кандидатов стратегий."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def run(self, context: ToolContext, prompt: str) -> Dict[str, Any]:
        """Возвращает отчёт по кандидату (используется в research_lab)."""

        generator = self.registry.resolve("generate_candidate")
        candidate = generator.execute(context, prompt=prompt)

        backtest_runner = self.registry.resolve("run_backtest")
        walkforward_runner = self.registry.resolve("run_walkforward")
        montecarlo_runner = self.registry.resolve("run_montecarlo")

        backtest = backtest_runner.execute(context, candidate=candidate)
        walkforward = walkforward_runner.execute(context, candidate=candidate)
        montecarlo = montecarlo_runner.execute(context, candidate=candidate)

        return {
            "candidate": candidate,
            "backtest": backtest,
            "walkforward": walkforward,
            "montecarlo": montecarlo,
        }
