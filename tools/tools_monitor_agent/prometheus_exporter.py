"""Инструмент экспорта метрик в Prometheus."""

from __future__ import annotations

from typing import Sequence

from brain_orchestrator.regimes import MarketRegime
from brain_orchestrator.tools.base import ToolContext, ToolSpec
from prod_core.exec.broker_ccxt import OrderResult
from prod_core.monitor.telemetry import TelemetryExporter


class PrometheusExporterTool:
    """Проксирует вызовы к TelemetryExporter."""

    spec = ToolSpec(
        capability="export_metrics",
        agent="monitor",
        read_only=False,
        safety_tags=("deterministic",),
        cost_hint_ms=5,
    )

    def __init__(self, telemetry: TelemetryExporter | None = None) -> None:
        from prod_core.monitor.telemetry import TelemetryExporter as Exporter

        self.telemetry = telemetry or Exporter()

    def execute(
        self,
        context: ToolContext,
        **kwargs,
    ) -> None:
        features = kwargs["features"]
        regime: MarketRegime = kwargs["regime"]
        executions: Sequence[OrderResult] = kwargs.get("executions", [])

        if executions:
            self.telemetry.record_agent_tool("execution", "place_order", 1, 0.01)


def register_tools(registry) -> None:
    registry.register(PrometheusExporterTool())
