"""Высокоуровневая обёртка вокруг BrainOrchestrator."""

from __future__ import annotations

import pandas as pd

from brain_orchestrator.brain import BrainOrchestrator


class BrainAgent:
    """Позволяет вызывать оркестратор как одного агента."""

    def __init__(self, orchestrator: BrainOrchestrator) -> None:
        self.orchestrator = orchestrator

    def run(self, candles: pd.DataFrame, state: dict[str, float], mode: str, symbol: str) -> None:
        """Проксирует запуск цикла оркестратора."""

        self.orchestrator.run_cycle(candles=candles, state=state, mode=mode, symbol=symbol)
