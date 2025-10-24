from __future__ import annotations

from pathlib import Path

from prod_core.exec.broker_ccxt import CCXTBroker, OrderRequest
from prod_core.exec.portfolio import PortfolioController
from prod_core.persist import PersistDAO


def test_ccxt_broker_simulation_without_credentials(tmp_path: Path) -> None:
    db_path = tmp_path / "paper.db"
    dao = PersistDAO(str(db_path), run_id="test-run")
    dao.initialize()
    portfolio = PortfolioController(dao=dao)

    broker = CCXTBroker(exchange="binanceusdm", dao=dao, portfolio=portfolio)
    result = broker.submit_orders(
        [
            OrderRequest(
                symbol="BTC/USDT:USDT",
                side="buy",
                quantity=0.01,
                price=30000.0,
                order_type="limit",
            )
        ]
    )

    assert len(result) == 1
    order = result[0]
    assert order.status == "filled"
    stored = dao.fetch_order_by_client(order.client_id)
    assert stored is not None
    assert stored["status"] == "filled"
