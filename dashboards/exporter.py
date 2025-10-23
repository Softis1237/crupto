"""Хелпер для старта Prometheus-экспортера."""

from __future__ import annotations

from prometheus_client import start_http_server

from prod_core.monitor.telemetry import TelemetryExporter


def serve_prometheus(telemetry: TelemetryExporter, port: int) -> None:
    """Запускает HTTP-сервер Prometheus поверх указанного реестра."""

    start_http_server(port, registry=telemetry.registry)
