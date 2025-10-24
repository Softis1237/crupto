"""РРЅС‚РµРіСЂР°С†РёРѕРЅРЅС‹Р№ С‚РµСЃС‚ РїР°Р№РїР»Р°Р№РЅР° prod_core.runner СЃ mock-С„РёРґРѕРј."""

from __future__ import annotations

import asyncio
import warnings
from pathlib import Path
from typing import Any

import pytest

from prod_core.monitor.telemetry import TelemetryExporter
from prod_core.persist import PersistDAO
from prod_core.runner import _run_paper_loop


def test_integration_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """РџСЂРѕРІРµСЂСЏРµС‚ РїРѕР»РЅС‹Р№ РїСѓС‚СЊ РґР°РЅРЅС‹С…: feed в†’ Р°РіРµРЅС‚С‹ в†’ DAO в†’ С‚РµР»РµРјРµС‚СЂРёСЏ."""

    db_path = tmp_path / "integration.db"
    run_id = "test_integration_pipeline"

    monkeypatch.setenv("PERSIST_DB_PATH", str(db_path))
    monkeypatch.setenv("RUN_ID", run_id)
    monkeypatch.setenv("MODE", "paper")
    monkeypatch.setenv("ENABLE_WS", "0")

    monkeypatch.setattr("prod_core.runner.serve_prometheus", lambda telemetry, port: None)

    from prod_core.exec.broker_ccxt import CCXTBroker

    monkeypatch.setattr(CCXTBroker, "_build_client", lambda self, exchange, params: None)

    class RecordingTelemetry(TelemetryExporter):
        """Р¤РёРєСЃРёСЂСѓРµС‚ РєР»СЋС‡РµРІС‹Рµ Р·РЅР°С‡РµРЅРёСЏ gauge-РјРµС‚СЂРёРє РґР»СЏ РїСЂРѕРІРµСЂРєРё."""

        instances: list["RecordingTelemetry"] = []

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["csv_path"] = str(tmp_path / "telemetry.csv")
            super().__init__(*args, **kwargs)
            self.feed_values: list[int] = []
            RecordingTelemetry.instances.append(self)

        def record_feed_health(self, value: int) -> None:
            self.feed_values.append(value)
            super().record_feed_health(value)

    monkeypatch.setattr("prod_core.runner.TelemetryExporter", RecordingTelemetry)

    warnings.filterwarnings("ignore", category=ResourceWarning)

    asyncio.run(
        _run_paper_loop(
            max_cycles=3,
            skip_feed_check=True,
            use_mock_feed=True,
        )
    )

    dao = PersistDAO(db_path, run_id=run_id)
    orders = dao.fetch_orders()
    positions = dao.fetch_positions()
    trades = dao.fetch_trades()

    assert orders, "РџР»Р°РЅ РёСЃРїРѕР»РЅРµРЅРёСЏ РґРѕР»Р¶РµРЅ СЃРѕС…СЂР°РЅРёС‚СЊ РѕСЂРґРµСЂР° РІ DAO."
    assert positions, "РџРѕСЃР»Рµ РёСЃРїРѕР»РЅРµРЅРёСЏ РѕР¶РёРґР°РµС‚СЃСЏ Р·Р°РїРёСЃСЊ РѕС‚РєСЂС‹С‚С‹С… РїРѕР·РёС†РёР№."
    assert trades, "РСЃРїРѕР»РЅРµРЅРёРµ РґРѕР»Р¶РЅРѕ РіРµРЅРµСЂРёСЂРѕРІР°С‚СЊ Р·Р°РїРёСЃРё РІ trades."

    latency_entries = dao.fetch_latency()
    stages = {entry["stage"] for entry in latency_entries}
    expected_stages = {"market_regime", "strategy_selection", "risk_manager", "execution", "monitor"}
    assert expected_stages.issubset(stages), "Р’СЃРµ СЃС‚Р°РґРёРё РїР°Р№РїР»Р°Р№РЅР° РґРѕР»Р¶РЅС‹ РїСѓР±Р»РёРєРѕРІР°С‚СЊ Р»Р°С‚РµРЅС‚РЅРѕСЃС‚СЊ."

    telemetry = RecordingTelemetry.instances[-1]
    assert len(telemetry.feed_values) == 3, "Должно быть ровно три измерения feed_health (по числу циклов)."
    assert telemetry.feed_values[-1] == 1, "Последнее значение feed_health должно быть 1 (OK)."
    assert telemetry.pnl_cum_r._value.get() >= 0.0
    assert telemetry.equity_usd._value.get() > 0.0

