"""Хелпер для старта Prometheus-экспортера.

Если порт занят, пытаемся подобрать свободный в небольшом диапазоне.
Если задан порт 0 — не запускаем сервер (т.е. выключаем экспорт).
"""

from __future__ import annotations

import logging
from typing import Optional

from prometheus_client import start_http_server

from prod_core.monitor.telemetry import TelemetryExporter

logger = logging.getLogger(__name__)


def serve_prometheus(telemetry: TelemetryExporter, port: int) -> None:
    """Запускает HTTP-сервер Prometheus поверх указанного реестра.

    Если порт занят, пробуем следующую портовую нумерацию до +10.
    Если порт == 0 — экспорт отключён (не поднимаем сервер).
    """

    if not port or port == 0:
        logger.info("PROMETHEUS disabled (port=0)")
        return

    max_tries = 10
    attempt_port: Optional[int] = port
    for i in range(max_tries + 1):
        try:
            start_http_server(attempt_port, registry=telemetry.registry)
            logger.info("Prometheus exporter started on port %s", attempt_port)
            return
        except OSError as exc:
            logger.warning("Port %s unavailable: %s", attempt_port, exc)
            attempt_port = port + (i + 1)

    logger.error("Unable to start Prometheus exporter on ports %s..%s, giving up.", port, port + max_tries)
