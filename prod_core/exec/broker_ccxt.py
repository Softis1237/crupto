"""Адаптер ccxt для безопасного paper-исполнения с персистентностью."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Iterable

from prod_core.exec.portfolio import PortfolioController
from prod_core.persist import OrderPayload, PersistDAO

try:
    import ccxt  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - в тестах допускается отсутствие ccxt
    ccxt = None

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OrderRequest:
    """Детерминированное представление заявки."""

    symbol: str
    side: str
    quantity: float
    price: float | None = None
    order_type: str = "limit"
    post_only: bool = True
    client_id: str | None = None


@dataclass(slots=True)
class OrderResult:
    """Результат выполнения заявки брокером."""

    client_id: str
    status: str
    filled: float
    avg_price: float | None
    raw: dict[str, Any]
    estimated_slippage: float = 0.0
    estimated_spread: float = 0.0


class CCXTBroker:
    """Прокси вокруг ccxt с защитой от live-исполнения."""

    def __init__(
        self,
        exchange: str,
        mode: str = "paper",
        *,
        dao: PersistDAO | None = None,
        portfolio: PortfolioController | None = None,
        **kwargs: Any,
    ) -> None:
        if mode.lower() != "paper":
            raise ValueError("Разрешён только MODE=paper до прохождения Acceptance.")
        self.mode = mode
        self.exchange_id = exchange
        self._client = self._build_client(exchange, kwargs)
        self.dao = dao
        self.portfolio = portfolio

    def _build_client(self, exchange: str, params: dict[str, Any]) -> Any:
        """Создаёт объект ccxt или mock."""

        if ccxt is None:
            logger.warning("ccxt не установлен, CCXTBroker работает в режиме-заглушке.")
            return None
        api_key = os.getenv("EXCHANGE_API_KEY") or params.get("apiKey")
        secret = os.getenv("EXCHANGE_API_SECRET") or params.get("secret")
        options = {"enableRateLimit": True, **params.get("options", {})}
        client = getattr(ccxt, exchange)({"apiKey": api_key, "secret": secret, "options": options})
        client.set_sandbox_mode(True)
        return client

    def submit_orders(self, requests: Iterable[OrderRequest]) -> list[OrderResult]:
        """Отправляет пакет заявок. В режиме-заглушке только логирует действия."""

        results: list[OrderResult] = []
        for request in requests:
            client_id = request.client_id or self._build_client_id(request)
            order_id = None
            already_filled = False

            if self.dao:
                existing = self.dao.fetch_order_by_client(client_id)
                if existing is None:
                    order_payload = OrderPayload(
                        ts=int(time.time()),
                        symbol=request.symbol,
                        side=request.side,
                        order_type=request.order_type,
                        qty=request.quantity,
                        price=request.price,
                        status="pending",
                        client_id=client_id,
                        exchange_id=self.exchange_id,
                        meta={"mode": self.mode},
                        run_id=self.dao.run_id if hasattr(self.dao, 'run_id') else None,
                    )
                    order_id = self.dao.insert_order(order_payload)
                else:
                    order_id = int(existing["id"])
                    already_filled = existing.get("status") == "filled"

            logger.info(
                "PAPER order: %s %s qty=%s price=%s id=%s",
                request.side,
                request.symbol,
                request.quantity,
                request.price,
                client_id,
            )

            if self._client is None:
                result = OrderResult(
                    client_id=client_id,
                    status="filled",
                    filled=request.quantity,
                    avg_price=request.price,
                    raw={"mode": "simulation", "order_id": order_id},
                )
                results.append(result)
                self._finalize_fill(
                    client_id=client_id,
                    order_id=order_id,
                    status=result.status,
                    qty=request.quantity,
                    price=request.price or 0.0,
                    already_filled=already_filled,
                    symbol=request.symbol,
                    side=request.side,
                )
                continue

            if request.order_type == "limit" and request.price is None:
                logger.error(
                    "Ошибка создания лимитного ордера: не указана цена (symbol=%s, side=%s, qty=%.6f)",
                    request.symbol, request.side, request.quantity
                )
                return [OrderResult(
                    client_id=client_id,
                    status="rejected",
                    filled=0.0,
                    avg_price=None,
                    raw={"error": "Price is required for limit orders"}
                )]

            params = {"postOnly": request.post_only}
            try:
                response = self._client.create_order(
                    symbol=request.symbol,
                    type=request.order_type,
                    side=request.side,
                    amount=request.quantity,
                    price=request.price,
                    params=params,
                )
                filled = float(response.get("filled", request.quantity))
                avg_price = float(response.get("average", request.price or 0.0)) if response.get("average") else request.price
                status = response.get("status", "open")
                result = OrderResult(
                    client_id=client_id,
                    status=status,
                    filled=filled,
                    avg_price=avg_price,
                    raw={**response, "order_id": order_id},
                )
                results.append(result)
                self._finalize_fill(
                    client_id=client_id,
                    order_id=order_id,
                    status=status,
                    qty=filled,
                    price=avg_price or 0.0,
                    already_filled=already_filled,
                    symbol=request.symbol,
                    side=request.side,
                )
            except Exception as exc:  # pragma: no cover - зависит от ccxt
                logger.exception("Ошибка при отправке заявки: id=%s exc=%s", client_id, exc)
                results.append(
                    OrderResult(
                        client_id=client_id,
                        status="error",
                        filled=0.0,
                        avg_price=None,
                        raw={"error": str(exc), "order_id": order_id},
                    )
                )
        return results

    def _finalize_fill(
        self,
        *,
        client_id: str,
        order_id: int | None,
        status: str,
        qty: float,
        price: float,
        already_filled: bool,
        symbol: str,
        side: str,
    ) -> None:
        """Фиксирует результат сделки в DAO и портфеле."""

        if not self.dao or order_id is None or already_filled:
            return
        self.dao.update_order_status(
            client_id,
            status=status,
            price=price,
            qty=qty,
        )
        status_lower = status.lower()
        if self.portfolio and qty > 0 and price > 0 and status_lower in {"filled", "closed"}:
            self.portfolio.apply_fill(
                order_id=order_id,
                symbol=symbol,
                side=side.lower(),
                qty=qty,
                price=price,
                fee=0.0,
            )

    def cancel_orders(self, client_ids: Iterable[str]) -> None:
        """Отменяет заявки по client_id."""

        for client_id in client_ids:
            logger.info("PAPER cancel: id=%s", client_id)
            if self.dao:
                self.dao.update_order_status(client_id, status="cancelled")

    @staticmethod
    def _build_client_id(order: OrderRequest) -> str:
        """Генерирует детерминированный идентификатор."""

        side = order.side.upper()
        qty = f"{order.quantity:.6f}"
        return f"{order.symbol.replace('/', '_')}-{side}-{qty}"

