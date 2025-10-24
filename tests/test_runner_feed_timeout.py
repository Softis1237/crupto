from __future__ import annotations

import asyncio
from pathlib import Path

from prod_core import runner as runner_module


class DummyFeed:
    def __init__(self, exchange_id: str, symbols, **kwargs) -> None:
        self.exchange_id = exchange_id
        self.symbols = symbols
        self.force_called = False

    async def __aenter__(self) -> "DummyFeed":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def wait_ready(self, symbol: str, timeframe: str, timeout: float | None = None) -> bool:
        assert timeout == 1.0
        return False

    def force_rest_mode(self) -> None:
        self.force_called = True

    def snapshot(self, *, min_bars: int | None = None):
        return {}

    def status(self):
        return {}


class DummyTelemetry:
    def __init__(self) -> None:
        self.feed_health: list[int] = []

    def record_feed_health(self, value: int) -> None:
        self.feed_health.append(value)


class DummyBrain:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def run_cycle(self, **kwargs) -> None:
        return None


class DummyRiskEngine:
    def __init__(self, *args, **kwargs) -> None:
        pass


def fake_connect_registry(*args, **kwargs):
    return object()


def test_runner_switches_to_rest_on_feed_timeout(monkeypatch, tmp_path: Path) -> None:
    created_feeds: list[DummyFeed] = []

    def make_feed(*args, **kwargs):
        feed = DummyFeed(*args, **kwargs)
        created_feeds.append(feed)
        return feed

    monkeypatch.setattr(runner_module, "MarketDataFeed", make_feed)
    monkeypatch.setattr(runner_module, "TelemetryExporter", lambda *a, **k: DummyTelemetry())
    monkeypatch.setattr(runner_module, "serve_prometheus", lambda *a, **k: None)
    monkeypatch.setattr(runner_module, "BrainOrchestrator", DummyBrain)
    monkeypatch.setattr(runner_module, "RiskEngine", DummyRiskEngine)
    monkeypatch.setattr(runner_module, "connect_registry", fake_connect_registry)
    monkeypatch.setattr(runner_module, "load_shadow_strategies", lambda *a, **k: [])

    async def fast_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(runner_module.asyncio, "sleep", fast_sleep)

    db_path = tmp_path / "paper.db"
    monkeypatch.setenv("PERSIST_DB_PATH", str(db_path))
    monkeypatch.setenv("PROMETHEUS_PORT", "0")

    async def run_loop() -> None:
        await runner_module._run_paper_loop(  # type: ignore[attr-defined]
            max_seconds=None,
            max_cycles=1,
            skip_feed_check=False,
            use_mock_feed=False,
            feed_timeout=1.0,
        )

    asyncio.run(run_loop())

    assert created_feeds, "feed was not instantiated"
    assert created_feeds[0].force_called, "feed.force_rest_mode() was not invoked"
