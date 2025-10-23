"""Агент исполнения заявок."""

from __future__ import annotations

from typing import List, Sequence

from brain_orchestrator.tools import ToolRegistry
from brain_orchestrator.tools.base import ToolContext
from prod_core.exec.broker_ccxt import OrderResult
from prod_core.strategies import StrategyPlan


class ExecutionAgent:
    """Проверяет ликвидность, оценивает сллипедж и отправляет заявки."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        portfolio=None,
        dao=None,
    ) -> None:
        self.registry = registry
        self.portfolio = portfolio
        self.dao = dao

    def run(self, context: ToolContext, plans: Sequence[StrategyPlan]) -> List[OrderResult]:
        """Возвращает результаты исполнения по одобренным планам."""

        if not plans:
            return []

        liquidity_tool = self.registry.resolve("check_liquidity")
        slippage_tool = self.registry.resolve("estimate_slippage")
        placer_tool = self.registry.resolve("place_order")

        results: List[OrderResult] = []
        for plan in plans:
            if not liquidity_tool.execute(context, plan=plan):
                continue
            slippage = slippage_tool.execute(context, plan=plan)
            result = placer_tool.execute(context, plan=plan, slippage=slippage)
            results.append(result)
        return results
