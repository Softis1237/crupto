"""Агент выбора стратегий в зависимости от режима."""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence

import pandas as pd

from brain_orchestrator.regimes import MarketRegime
from brain_orchestrator.tools import ToolRegistry
from brain_orchestrator.tools.base import ToolContext
from prod_core.strategies import TradingStrategy


class StrategySelectionAgent:
    """Применяет enable map, скоринг и cooldown."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry
        self.cooldown_state: Dict[str, dict] = {}

    def run(
        self,
        context: ToolContext,
        strategies: Sequence[TradingStrategy],
        regime: MarketRegime,
        features: pd.DataFrame,
    ) -> List[TradingStrategy]:
        """Возвращает стратегии, допущенные к исполнению."""

        enable_tool = self.registry.resolve("load_enable_map")
        score_tool = self.registry.resolve("score_strategy")
        cooldown_tool = self.registry.resolve("manage_cooldown")

        enable_map = enable_tool.execute(context)
        regime_key = regime.name.lower()
        allowed = set(enable_map.get(regime_key, []))

        selected: List[TradingStrategy] = []
        for strategy in strategies:
            if strategy.name not in allowed:
                continue
            score = score_tool.execute(context, strategy=strategy, features=features)
            if score < 0:
                continue
            cooldown_ok = cooldown_tool.execute(
                context,
                strategy=strategy,
                cooldown_state=self.cooldown_state,
            )
            if not cooldown_ok:
                continue
            selected.append(strategy)
        return selected
