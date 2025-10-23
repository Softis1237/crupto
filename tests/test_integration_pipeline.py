"""Интеграционный тест пайплайна prod_core.runner с mock-фидом."""

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
    """Проверяет полный путь данных: feed → агенты → DAO → телеметрия."""

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
        """Фиксирует ключевые значения gauge-метрик для проверки."""

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
            max_cycles=5,
            skip_feed_check=True,
            use_mock_feed=True,
        )
    )

    dao = PersistDAO(db_path, run_id=run_id)
    orders = dao.fetch_orders()
    positions = dao.fetch_positions()
    trades = dao.fetch_trades()

    assert orders, "План исполнения должен сохранить ордера в DAO."
    assert positions, "После исполнения ожидается запись открытых позиций."
    assert trades, "Исполнение должно генерировать записи в trades."

    latency_entries = dao.fetch_latency()
    stages = {entry["stage"] for entry in latency_entries}
    expected_stages = {"market_regime", "strategy_selection", "risk_manager", "execution", "monitor"}
    assert expected_stages.issubset(stages), "Все стадии пайплайна должны публиковать латентность."

    telemetry = RecordingTelemetry.instances[-1]
    assert len(telemetry.feed_values) == 5, "Должно быть ровно пять измерений feed_health (по числу циклов)."
    assert telemetry.feed_health._value.get() in (0, 1)
    assert telemetry.pnl_cum_r._value.get() >= 0.0
    assert telemetry.equity_usd._value.get() > 0.0
