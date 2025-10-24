"""Экспорт телеметрии в Prometheus и вспомогательные стореджи."""

from __future__ import annotations

import csv
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from prod_core.persist import PersistDAO

from prometheus_client import CollectorRegistry, Gauge, Histogram


@dataclass(slots=True)
class TelemetryEvent:
    """Запись телеметрии для CSV/SQLite."""

    timestamp: float
    event_type: str
    payload: dict[str, Any]


class TelemetryExporter:
    """Используется ядром для публикации метрик состояния."""

    def __init__(self, registry: CollectorRegistry | None = None, csv_path: str | None = None) -> None:
        self.registry = registry or CollectorRegistry()
        self.csv_path = Path(csv_path) if csv_path else None
        if self.csv_path:
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)

        self.agent_tool_state = Gauge(
            "agent_tool_state",
            "Состояние инструмента агента (0 off, 1 ok, 2 warn, 3 error)",
            labelnames=("agent", "tool"),
            registry=self.registry,
        )
        self.agent_tool_latency = Histogram(
            "agent_tool_latency_seconds",
            "Латентность выполнения инструмента, секунды",
            labelnames=("agent", "tool"),
            registry=self.registry,
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
        )
        self.agent_edge_state = Gauge(
            "agent_edge_state",
            "Состояние взаимодействия между агентами (1 ok, 2 warn, 3 error)",
            labelnames=("src", "dst"),
            registry=self.registry,
        )
        self.stage_latency = Histogram(
            "stage_latency_seconds",
            "Латентность этапов пайплайна (feed→execution).",
            labelnames=("stage",),
            registry=self.registry,
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
        )
        self.feed_health = Gauge("feed_health", "Статус фида (1 ok, 0 degraded)", registry=self.registry)
        self.dd_state = Gauge("dd_state", "Текущий drawdown портфеля, %", registry=self.registry)
        self.daily_lock_state = Gauge(
            "daily_lock_state",
            "Статус дневного замка (0 off, 1 locked)",
            labelnames=("reason",),
            registry=self.registry,
        )
        self.regime_label = Gauge("regime_label", "Код текущего рыночного режима", registry=self.registry)
        self.pnl_cum_r = Gauge("pnl_cum_r", "Кумулятивный PnL в R-множителях", registry=self.registry)
        self.winrate = Gauge("winrate", "Процент выигрышных сделок (0-1)", registry=self.registry)
        self.avg_win_r = Gauge("avg_win_r", "Средний выигрыш в R", registry=self.registry)
        self.avg_loss_r = Gauge("avg_loss_r", "Средний проигрыш в R", registry=self.registry)
        self.max_dd_r = Gauge("max_dd_r", "Максимальная просадка в R за 72h", registry=self.registry)
        self.slippage_ratio = Histogram(
            "execution_slippage_ratio",
            "Относительный сллипедж исполнения (|fill-price - mid| / mid).",
            registry=self.registry,
            buckets=(0.0001, 0.0005, 0.001, 0.0025, 0.005, 0.01),
        )
        self.spread_pct = Histogram(
            "execution_spread_pct",
            "Спред инструмента в процентах.",
            registry=self.registry,
            buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.02),
        )
        self.reject_rate = Gauge(
            "execution_reject_rate",
            "Доля отклонённых планов исполнения (0-1).",
            registry=self.registry,
        )
        self.equity_usd = Gauge("equity_usd", "Текущая стоимость портфеля в USD", registry=self.registry)
        self.exposure_gross_pct = Gauge(
            "exposure_gross_pct",
            "Совокупная (gross) экспозиция в процентах от equity.",
            registry=self.registry,
        )
        self.exposure_net_pct = Gauge(
            "exposure_net_pct",
            "Чистая (net) экспозиция в процентах от equity.",
            registry=self.registry,
        )
        self.open_positions_count = Gauge(
            "open_positions_count",
            "Количество открытых позиций.",
            registry=self.registry,
        )
        self.portfolio_safe_mode = Gauge(
            "portfolio_safe_mode",
            "Portfolio safe-mode flag (1 enabled).",
            registry=self.registry,
        )
        self.runner_last_cycle_ts = Gauge(
            "runner_last_cycle_ts",
            "Unix timestamp of last orchestrator cycle.",
            registry=self.registry,
        )
        self._daily_lock_label: str | None = None
        self.stage_latency_ms = Histogram(
            "stage_latency_ms",
            "Латентность этапов пайплайна в миллисекундах.",
            labelnames=("stage",),
            registry=self.registry,
            buckets=(5, 10, 25, 50, 100, 250, 500, 1000, 2000),
        )

    def record_agent_tool(self, agent: str, tool: str, state: int, latency_seconds: float) -> None:
        """Публикует статус и латентность инструмента."""

        self.agent_tool_state.labels(agent=agent, tool=tool).set(state)
        self.agent_tool_latency.labels(agent=agent, tool=tool).observe(latency_seconds)

    def record_edge_state(self, src: str, dst: str, state: int) -> None:
        """Обновляет состояние ребра между агентами."""

        self.agent_edge_state.labels(src=src, dst=dst).set(state)

    def record_feed_health(self, status: int) -> None:
        """Выставляет метрику здоровья фида."""

        self.feed_health.set(status)

    def record_drawdown(self, drawdown_pct: float) -> None:
        """Фиксирует drawdown, чтобы мониторить kill-switch."""

        self.dd_state.set(drawdown_pct)

    def record_daily_lock(self, locked: bool, reason: str | None = None) -> None:
        """Record/update daily-lock state."""

        reason_label = (reason or "limits_ok").strip() or "limits_ok"
        if not locked:
            reason_label = "limits_ok"
        if getattr(self, '_daily_lock_label', None) and self._daily_lock_label != reason_label:
            self.daily_lock_state.labels(reason=self._daily_lock_label).set(0)
        self.daily_lock_state.labels(reason=reason_label).set(int(locked))
        self._daily_lock_label = reason_label

    def record_regime(self, regime_code: int) -> None:
        """Записывает код рыночного режима."""

        self.regime_label.set(regime_code)

    def record_performance(
        self,
        *,
        pnl_cum_r: float,
        winrate: float,
        avg_win_r: float,
        avg_loss_r: float,
        max_dd_r: float,
    ) -> None:
        """Публикует торговые метрики производительности."""

        self.pnl_cum_r.set(pnl_cum_r)
        self.winrate.set(winrate)
        self.avg_win_r.set(avg_win_r)
        self.avg_loss_r.set(avg_loss_r)
        self.max_dd_r.set(max_dd_r)

    def observe_execution(self, slippage: float | None, spread: float | None) -> None:
        """Фиксирует метрики исполнения."""

        if slippage is not None and slippage >= 0:
            self.slippage_ratio.observe(slippage)
        if spread is not None and spread >= 0:
            self.spread_pct.observe(spread)

    def record_reject_rate(self, rate: float) -> None:
        """Обновляет процент отклонённых заявок."""

        self.reject_rate.set(max(0.0, min(rate, 1.0)))

    def observe_stage_latency(self, stage: str, seconds: float) -> None:
        """Добавляет наблюдение латентности для указанной стадии пайплайна."""

        self.stage_latency.labels(stage=stage).observe(max(seconds, 0.0))
        self.stage_latency_ms.labels(stage=stage).observe(max(seconds * 1000, 0.0))

    def record_portfolio_safe_mode(self, enabled: bool) -> None:
        """Записывает состояние safe-mode портфеля."""

        self.portfolio_safe_mode.set(1 if enabled else 0)

    def record_cycle_heartbeat(self) -> None:
        """Update heartbeat timestamp for deadman alert."""

        self.runner_last_cycle_ts.set(time.time())

    def update_from_persist(self, dao: PersistDAO) -> None:
        """Обновляет метрики из персист-слоя."""

        snapshot = dao.fetch_equity_last()
        positions = dao.fetch_positions()

        if snapshot:
            self.equity_usd.set(float(snapshot.get("equity_usd", 0.0)))
            self.pnl_cum_r.set(float(snapshot.get("pnl_r_cum", 0.0)))
            self.max_dd_r.set(float(snapshot.get("max_dd_r", 0.0)))
            self.exposure_gross_pct.set(float(snapshot.get("exposure_gross", 0.0)))
            self.exposure_net_pct.set(float(snapshot.get("exposure_net", 0.0)))
        else:
            self.equity_usd.set(0.0)
            self.exposure_gross_pct.set(0.0)
            self.exposure_net_pct.set(0.0)

        self.open_positions_count.set(len(positions))

        trades = dao.fetch_trades(limit=100)
        if trades:
            wins = [trade for trade in trades if float(trade.get("pnl_r", 0.0)) > 0]
            losses = [trade for trade in trades if float(trade.get("pnl_r", 0.0)) < 0]
            total = len(wins) + len(losses)
            self.winrate.set(len(wins) / total if total else 0.0)
            avg_win = sum(float(t.get("pnl_r", 0.0)) for t in wins) / len(wins) if wins else 0.0
            avg_loss = sum(float(t.get("pnl_r", 0.0)) for t in losses) / len(losses) if losses else 0.0
            self.avg_win_r.set(avg_win)
            self.avg_loss_r.set(abs(avg_loss))
        else:
            self.winrate.set(0.0)
            self.avg_win_r.set(0.0)
            self.avg_loss_r.set(0.0)
    def apply_alert_overrides(self) -> None:
        """Apply alert overrides from environment (for testing)."""

        feed_override = os.getenv("ALERT_TEST_FEED_HEALTH")
        if feed_override:
            value = feed_override.lower()
            if value in {"bad", "down", "0"}:
                self.feed_health.set(0)
            elif value in {"good", "up", "1"}:
                self.feed_health.set(1)

        lock_override = os.getenv("ALERT_TEST_DAILY_LOCK")
        if lock_override:
            value = lock_override.lower()
            if value in {"off", "0", "reset"}:
                self.record_daily_lock(False, reason="limits_ok")
            else:
                self.record_daily_lock(True, reason=value)

        safe_override = os.getenv("ALERT_TEST_SAFE_MODE")
        if safe_override:
            value = safe_override.lower()
            if value in {"off", "0", "reset"}:
                self.record_portfolio_safe_mode(False)
            else:
                self.record_portfolio_safe_mode(True)

    def persist_event(self, event: TelemetryEvent) -> None:
        """Сохраняет событие телеметрии в CSV (для SQLite оставить хук)."""

        if not self.csv_path:
            return
        file_exists = self.csv_path.exists()
        with self.csv_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp", "event_type", "payload"])
            if not file_exists:
                writer.writeheader()
            row = asdict(event)
            row["payload"] = str(row["payload"])
            writer.writerow(row)

