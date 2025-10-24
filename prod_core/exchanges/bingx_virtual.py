from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, List

from prod_core.exec.broker_ccxt import CCXTBroker, OrderRequest, OrderResult
from prod_core.exec.portfolio import PortfolioController
from prod_core.persist import PersistDAO

logger = logging.getLogger(__name__)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class VirtualTradeArtifacts:
    """Артефакты тестового paper-цикла в режиме VST."""

    open_order: OrderResult
    close_order: OrderResult
    position_snapshot: dict[str, Any]
    orders: List[dict[str, Any]]
    trades: List[dict[str, Any]]


def run_virtual_vst_cycle(
    *,
    dao: PersistDAO,
    portfolio: PortfolioController | None = None,
    quantity: float = 1.0,
    symbol: str = "VST/USDT:USDT",
    limit_price: float = 1.0,
) -> VirtualTradeArtifacts:
    """
    Выполняет открытие и закрытие позиции VST/USDT в paper-режиме через CCXTBroker.

    Функция требует включённого USE_VIRTUAL_TRADING и установленного VIRTUAL_ASSET,
    чтобы ордера и позиции были помечены sandbox-метаданными.
    """

    if not _env_flag("USE_VIRTUAL_TRADING"):
        raise RuntimeError("USE_VIRTUAL_TRADING must be enabled for virtual cycle.")
    virtual_asset = os.getenv("VIRTUAL_ASSET")
    if not virtual_asset:
        raise RuntimeError("VIRTUAL_ASSET must be set (e.g. VST) for virtual cycle.")
    if not dao.run_id:
        raise ValueError("PersistDAO must be initialised with run_id for virtual cycle.")

    portfolio = portfolio or PortfolioController(dao=dao)
    broker = CCXTBroker(exchange="bingx", dao=dao, portfolio=portfolio)

    open_order = broker.submit_orders(
        [
            OrderRequest(
                symbol=symbol,
                side="buy",
                quantity=quantity,
                price=limit_price,
                order_type="limit",
                post_only=True,
            )
        ]
    )[0]

    position_snapshot = dao.fetch_position(symbol)
    if position_snapshot is None:
        raise RuntimeError("Position not recorded after opening virtual order.")

    close_order = broker.submit_orders(
        [
            OrderRequest(
                symbol=symbol,
                side="sell",
                quantity=quantity,
                price=limit_price,
                order_type="limit",
                post_only=True,
            )
        ]
    )[0]

    orders = dao.fetch_orders(run_id=dao.run_id)
    trades = dao.fetch_trades(run_id=dao.run_id)

    logger.info(
        "Completed virtual VST cycle: open_status=%s close_status=%s",
        open_order.status,
        close_order.status,
    )

    return VirtualTradeArtifacts(
        open_order=open_order,
        close_order=close_order,
        position_snapshot=position_snapshot,
        orders=orders,
        trades=trades,
    )
