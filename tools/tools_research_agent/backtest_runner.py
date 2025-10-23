"""Запуск бэктеста кандидата (заглушка)."""

from __future__ import annotations

from random import Random
from typing import Any

from brain_orchestrator.tools.base import ToolContext, ToolSpec


class BacktestRunnerTool:
    """Возвращает детерминированный отчёт о бэктесте."""

    spec = ToolSpec(
        capability="run_backtest",
        agent="research",
        read_only=True,
        safety_tags=("deterministic", "sandbox_only"),
        cost_hint_ms=200,
    )

    def execute(self, context: ToolContext, **kwargs) -> dict[str, Any]:
        candidate = kwargs["candidate"]
        rng = Random(candidate["id"])
        return {
            "pf": round(1.1 + rng.random() * 0.4, 3),
            "sharpe": round(0.9 + rng.random() * 0.6, 3),
            "max_dd": round(2 + rng.random() * 3, 2),
            "trades": int(150 + rng.random() * 150),
        }


def register_tools(registry) -> None:
    registry.register(BacktestRunnerTool())
