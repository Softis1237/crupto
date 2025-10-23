# Спецификация метрик Prometheus

- `agent_tool_state{agent,tool}` — Gauge: состояние инструментов (0 off, 1 ok, 2 warn, 3 error).
- `agent_tool_latency_seconds{agent,tool}` — Histogram: латентность выполнения инструмента (5ms–5s).
- `agent_edge_state{src,dst}` — Gauge: статус взаимодействия агентов (1 ok, 2 warn, 3 error).
- `stage_latency_seconds{stage}` — Histogram: латентность стадий пайплайна (market_regime, strategy_selection, risk_manager, execution, monitor).
- `feed_health` — Gauge: здоровье фида (1 ok, 0 degraded, -1 paused) обновляется runner'ом.
- `dd_state` — Gauge: текущий портфельный drawdown, %.
- `daily_lock_state` — Gauge: индикатор дневного замка (0/1).
- `regime_label` — Gauge: числовой код рыночного режима.
- `pnl_cum_r` — Gauge: накопленный PnL в R-множителях.
- `winrate` — Gauge: доля выигрышных сделок (0–1).
- `avg_win_r`, `avg_loss_r` — Gauge: средние R выигрышей и проигрышей (модуль).
- `max_dd_r` — Gauge: максимальная просадка в R за окно наблюдения.
- `execution_slippage_ratio` — Histogram: относительный сллипедж исполнения.
- `execution_spread_pct` — Histogram: наблюдаемый спред в процентах.
- `execution_reject_rate` — Gauge: доля отклонённых/ошибочных заявок (0–1).
- `equity_usd` — Gauge: фактический equity портфеля в USD (из DAO).
- `exposure_gross_pct`, `exposure_net_pct` — Gauge: совокупная и чистая экспозиции (% от equity).
- `open_positions_count` — Gauge: количество открытых позиций.
- `portfolio_safe_mode` — Gauge: состояние safe-mode портфеля (1 активен).
- `stage_latency_ms{stage}` — Histogram: латентность стадий в миллисекундах (для панелей Grafana).

Все метрики публикуются через `TelemetryExporter`, HTTP-эндпоинт Prometheus слушает порт `PROMETHEUS_PORT` (по умолчанию 9108).
