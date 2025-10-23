"""Высокоуровневая обёртка вокруг BrainOrchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from brain_orchestrator.brain import BrainOrchestrator


class BrainAgent:
    """Позволяет вызывать оркестратор как одного агента."""

    def __init__(self, orchestrator: "BrainOrchestrator") -> None:
        self.orchestrator = orchestrator

    def run(self, candles: pd.DataFrame, state: dict[str, float], mode: str, symbol: str, timeframe: str) -> None:
        """Проксирует запуск цикла оркестратора."""

        self.orchestrator.run_cycle(candles=candles, state=state, mode=mode, symbol=symbol, timeframe=timeframe)
