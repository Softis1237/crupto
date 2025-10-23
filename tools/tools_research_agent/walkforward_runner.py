"""Псевдо walk-forward в sandbox."""

from __future__ import annotations

from random import Random
from typing import Any

from brain_orchestrator.tools.base import ToolContext, ToolSpec


class WalkforwardRunnerTool:
    """Возвращает результат walk-forward оценки."""

    spec = ToolSpec(
        capability="run_walkforward",
        agent="research",
        read_only=True,
        safety_tags=("deterministic", "sandbox_only"),
        cost_hint_ms=250,
    )

    def execute(self, context: ToolContext, **kwargs) -> dict[str, Any]:
        candidate = kwargs["candidate"]
        rng = Random(candidate["id"] + "-wf")
        return {
            "pf": round(0.95 + rng.random() * 0.3, 3),
            "sharpe": round(0.8 + rng.random() * 0.5, 3),
            "max_dd": round(2.5 + rng.random() * 2.0, 2),
        }


def register_tools(registry) -> None:
    registry.register(WalkforwardRunnerTool())
