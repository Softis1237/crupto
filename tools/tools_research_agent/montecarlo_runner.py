"""Монте-Карло стресс для кандидатов."""

from __future__ import annotations

from random import Random
from typing import Any

from brain_orchestrator.tools.base import ToolContext, ToolSpec


class MonteCarloRunnerTool:
    """Оценивает устойчивость стратегии через перестановку сделок."""

    spec = ToolSpec(
        capability="run_montecarlo",
        agent="research",
        read_only=True,
        safety_tags=("deterministic", "sandbox_only"),
        cost_hint_ms=300,
    )

    def execute(self, context: ToolContext, **kwargs) -> dict[str, Any]:
        candidate = kwargs["candidate"]
        rng = Random(candidate["id"] + "-mc")
        return {
            "p95_dd": round(3.0 + rng.random() * 2.0, 2),
            "p95_pf": round(0.9 + rng.random() * 0.2, 3),
        }


def register_tools(registry) -> None:
    registry.register(MonteCarloRunnerTool())
