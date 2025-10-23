import time
from pathlib import Path

import pytest

from prod_core.persist import (
    EquitySnapshotPayload,
    LatencyPayload,
    OrderPayload,
    PersistDAO,
    PositionPayload,
    TradePayload,
)


@pytest.fixture()
def dao(tmp_path: Path) -> PersistDAO:
    db_path = tmp_path / "crupto_test.db"
    dao = PersistDAO(db_path, run_id="test-run")
    dao.initialize()
    return dao


def test_order_idempotency(dao: PersistDAO) -> None:
    payload = OrderPayload(
        ts=int(time.time()),
        symbol="BTC/USDT",
        side="buy",
        order_type="limit",
        qty=1.0,
        price=20000.0,
        status="pending",
        client_id="order-1",
        exchange_id="binanceusdm",
    )
    first_id = dao.insert_order(payload)
    second_id = dao.insert_order(payload)
    assert first_id == second_id

    dao.update_order_status("order-1", status="filled", price=20100.0, qty=1.0)
    stored = dao.fetch_order_by_client("order-1")
    assert stored is not None
    assert stored["status"] == "filled"
    assert float(stored["price"]) == 20100.0
    assert stored["run_id"] == "test-run"


def test_trade_and_positions_flow(dao: PersistDAO) -> None:
    order_id = dao.insert_order(
        OrderPayload(
            ts=int(time.time()),
            symbol="ETH/USDT",
            side="sell",
            order_type="limit",
            qty=2.0,
            price=1500.0,
            status="pending",
            client_id="trade-1",
            exchange_id="binanceusdm",
        )
    )

    trade_id = dao.insert_trade(
        TradePayload(
            order_id=order_id,
            ts=int(time.time()),
            symbol="ETH/USDT",
            side="sell",
            qty=1.0,
            price=1510.0,
            fee=0.5,
            pnl_r=0.25,
        )
    )
    assert trade_id > 0

    dao.upsert_position(
        PositionPayload(
            symbol="ETH/USDT",
            ts=int(time.time()),
            qty=1.0,
            avg_price=1505.0,
            unrealized_pnl_r=0.0,
            realized_pnl_r=0.25,
            exposure_usd=1505.0,
            meta={"last_price": 1510.0},
        )
    )
    positions = dao.fetch_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "ETH/USDT"
    assert positions[0]["run_id"] == "test-run"

    dao.clear_position("ETH/USDT")
    assert dao.fetch_positions() == []


def test_equity_snapshot_and_latency(dao: PersistDAO) -> None:
    now = int(time.time())
    dao.insert_equity_snapshot(
        EquitySnapshotPayload(
            ts=now,
            equity_usd=10000.0,
            pnl_r_cum=1.5,
            max_dd_r=0.4,
            exposure_gross=25.0,
            exposure_net=5.0,
        )
    )
    snapshot = dao.fetch_equity_last()
    assert snapshot is not None
    assert float(snapshot["equity_usd"]) == 10000.0
    assert float(snapshot["pnl_r_cum"]) == 1.5
    assert snapshot["run_id"] == "test-run"

    dao.insert_latency(
        LatencyPayload(
            ts=now,
            stage="risk_manager",
            ms=12.5,
        )
    )
    with dao._connect() as conn:  # type: ignore[attr-defined]
        row = conn.execute("SELECT run_id FROM latency").fetchone()
    assert row is not None and row["run_id"] == "test-run"
