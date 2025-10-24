from __future__ import annotations

from pathlib import Path

import pytest

from prod_core.exec.portfolio import PortfolioController
from prod_core.exchanges import VirtualTradeArtifacts, run_virtual_vst_cycle
from prod_core.persist import PersistDAO


@pytest.fixture
def dao(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PersistDAO:
    db_path = tmp_path / "virtual.db"

    monkeypatch.setenv("USE_VIRTUAL_TRADING", "true")
    monkeypatch.setenv("VIRTUAL_ASSET", "VST")
    monkeypatch.setenv("VIRTUAL_EQUITY", "15000")
    monkeypatch.delenv("EXCHANGE_API_KEY", raising=False)
    monkeypatch.delenv("EXCHANGE_API_SECRET", raising=False)

    instance = PersistDAO(str(db_path), run_id="virtual-test-run")
    instance.initialize()
    return instance


def test_run_virtual_vst_cycle_records_virtual_metadata(
    dao: PersistDAO, monkeypatch: pytest.MonkeyPatch
) -> None:
    portfolio = PortfolioController(dao=dao)

    artifacts: VirtualTradeArtifacts = run_virtual_vst_cycle(
        dao=dao,
        portfolio=portfolio,
        quantity=0.25,
        limit_price=1.0,
        symbol="VST/USDT:USDT",
    )

    assert artifacts.open_order.status == "filled"
    assert artifacts.close_order.status == "filled"
    assert artifacts.open_order.raw.get("virtual_asset") == "VST"
    assert artifacts.close_order.raw.get("virtual_asset") == "VST"

    position_meta = artifacts.position_snapshot.get("meta") or {}
    assert position_meta.get("virtual_asset") == "VST"
    assert artifacts.position_snapshot.get("symbol") == "VST/USDT:USDT"

    # Orders persisted in DAO must retain virtual markers for analysis.
    assert artifacts.orders, "orders must be recorded in DAO for virtual cycle"
    for order in artifacts.orders:
        meta = order.get("meta") or {}
        assert meta.get("virtual_asset") == "VST"
        assert meta.get("use_virtual_trading") is True

    # There should be at least one trade with virtual metadata (open leg).
    assert artifacts.trades, "virtual cycle must produce trade records"
    trade_meta = artifacts.trades[0].get("meta") or {}
    assert trade_meta.get("virtual_asset") == "VST"
