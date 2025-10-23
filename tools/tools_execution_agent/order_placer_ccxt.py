"""Инструмент отправки заявок через CCXTBroker."""

from __future__ import annotations

import time

from brain_orchestrator.tools.base import ToolContext, ToolSpec
from prod_core.exec.broker_ccxt import CCXTBroker, OrderRequest, OrderResult
from prod_core.exec.portfolio import PortfolioController
from prod_core.persist import PersistDAO
from prod_core.strategies import StrategyPlan


class OrderPlacerTool:
    """Конвертирует план в заявку и отправляет через CCXT broker."""

    spec = ToolSpec(
        capability="place_order",
        agent="execution",
        read_only=False,
        safety_tags=("deterministic", "paper_mode_only"),
        cost_hint_ms=15,
    )

    def __init__(self, exchange: str = "binanceusdm") -> None:
        self._exchange = exchange
        self._broker = CCXTBroker(exchange=exchange, mode="paper")
        self._dao: PersistDAO | None = None
        self._portfolio: PortfolioController | None = None

    def configure_persistence(
        self,
        dao: PersistDAO,
        portfolio: PortfolioController,
        exchange: str | None = None,
    ) -> None:
        """Инжектит DAO и портфельный учёт."""

        self._dao = dao
        self._portfolio = portfolio
        if exchange and exchange != self._exchange:
            self._exchange = exchange
            self._broker = CCXTBroker(exchange=exchange, mode="paper", dao=dao, portfolio=portfolio)
        else:
            self._broker.dao = dao
            self._broker.portfolio = portfolio

    def execute(self, context: ToolContext, **kwargs) -> OrderResult:
        plan: StrategyPlan = kwargs["plan"]
        slippage = float(kwargs.get("slippage") or 0.0)
        side = plan.signal.side
        price = plan.signal.metadata.get("entry_price")
        request = OrderRequest(
            symbol=context.symbol,
            side="buy" if side == "long" else "sell",
            quantity=plan.size,
            price=price,
        )
        if self._dao is not None:
            origin_ts = int(plan.signal.timestamp.timestamp()) if hasattr(plan.signal, "timestamp") else int(time.time())
            request.client_id = (
                f"{context.symbol.replace('/', '_')}-{request.side.upper()}-{origin_ts}-{plan.size:.6f}"
            )
        result = self._broker.submit_orders([request])[0]
        result.estimated_slippage = slippage
        result.estimated_spread = float(plan.signal.metadata.get("spread", 0.0) or 0.0)
        return result


def register_tools(registry) -> None:
    registry.register(OrderPlacerTool())
