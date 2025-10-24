from __future__ import annotations

import os

from prometheus_client import CollectorRegistry

from prod_core.monitor.telemetry import TelemetryExporter


def _gauge_value(metric: TelemetryExporter, attr: str) -> float:
    gauge = getattr(metric, attr)
    return gauge._value.get()  # type: ignore[attr-defined]


def test_record_daily_lock_tracks_reason() -> None:
    telemetry = TelemetryExporter(CollectorRegistry())
    telemetry.record_daily_lock(True, reason="max_daily_loss")
    samples = telemetry.daily_lock_state.collect()[0].samples
    assert any(s.labels.get("reason") == "max_daily_loss" and s.value == 1 for s in samples)

    telemetry.record_daily_lock(False)
    samples = telemetry.daily_lock_state.collect()[0].samples
    assert any(s.labels.get("reason") == "limits_ok" and s.value == 0 for s in samples)


def test_cycle_heartbeat_updates_timestamp() -> None:
    telemetry = TelemetryExporter(CollectorRegistry())
    telemetry.record_cycle_heartbeat()
    assert _gauge_value(telemetry, "runner_last_cycle_ts") > 0


def test_apply_alert_overrides_env() -> None:
    telemetry = TelemetryExporter(CollectorRegistry())
    os.environ["ALERT_TEST_FEED_HEALTH"] = "bad"
    os.environ["ALERT_TEST_DAILY_LOCK"] = "kill"
    os.environ["ALERT_TEST_SAFE_MODE"] = "on"
    try:
        telemetry.apply_alert_overrides()
        assert _gauge_value(telemetry, "feed_health") == 0
        samples = telemetry.daily_lock_state.collect()[0].samples
        assert any(s.labels.get("reason") == "kill" and s.value == 1 for s in samples)
        assert _gauge_value(telemetry, "portfolio_safe_mode") == 1
    finally:
        for key in ["ALERT_TEST_FEED_HEALTH", "ALERT_TEST_DAILY_LOCK", "ALERT_TEST_SAFE_MODE"]:
            os.environ.pop(key, None)
