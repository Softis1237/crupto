"""Агент мониторинга телеметрии."""

from __future__ import annotations

from typing import Sequence

import pandas as pd

from brain_orchestrator.regimes import MarketRegime
from brain_orchestrator.tools import ToolRegistry
from brain_orchestrator.tools.base import ToolContext
from prod_core.exec.broker_ccxt import OrderResult
from prod_core.monitor.telemetry import TelemetryExporter
from prod_core.persist import PersistDAO


class MonitorAgent:
    """Отвечает за экспорт метрик и обновление состояний в Prometheus."""

    def __init__(self, registry: ToolRegistry, telemetry: TelemetryExporter, dao: PersistDAO) -> None:
        self.registry = registry
        self.telemetry = telemetry
        self.dao = dao

    def run(
        self,
        context: ToolContext,
        features: pd.DataFrame,
        regime: MarketRegime,
        executions: Sequence[OrderResult],
    ) -> None:
        """Экспортирует метрики и обновляет health-статусы."""

        exporter = self.registry.resolve("export_metrics")
        exporter.execute(context, features=features, regime=regime, executions=executions)
        rejects = 0

        for execution in executions:
            self.telemetry.observe_execution(execution.estimated_slippage, execution.estimated_spread)
            if execution.status.lower() in {"error", "rejected", "cancelled"}:
                rejects += 1

        if executions:
            self.telemetry.record_reject_rate(rejects / len(executions))
        self.telemetry.update_from_persist(self.dao)
        self.telemetry.record_regime(regime.value)
        self.telemetry.apply_alert_overrides()
