# Grafana: мозг-дерево
- Datasource: Prometheus (см. dashboards/grafana/datasources.yml).
- Метрики: agent_tool_state/latency, agent_edge_state, stage_latency_seconds, feed_health, dd_state, daily_lock_state, regime_label, pnl_cum_r, max_dd_r, winrate, execution_slippage_ratio, execution_reject_rate.
- Цвета статусов: 1=зелёный, 2=жёлтый, 3=красный, 0/нет данных=серый.
- Панели: Node Graph (агенты/инструменты, рёбра agent_edge_state), Status History (feed & risk), Bar gauge (stage latency), Timeseries (PnL/DD/Winrate).
- При добавлении агента/инструмента → обновите exporter, dashboard.json и README.
