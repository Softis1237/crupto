# Acceptance checklist (MVP paper)

- [ ] Pytest coverage ≥ 70% для `prod_core`, `brain_orchestrator`, `tools`.
- [ ] 24h paper-гонка без критических ошибок, подтверждены kill-switch и daily-lock.
- [x] Prometheus экспортирует: agent_tool_state, agent_edge_state, stage_latency_seconds, feed_health, dd_state, daily_lock_state, regime_label, pnl/slippage/spread.
- [ ] Grafana Node Graph подсвечивает агентов/инструменты; панели latency и regime обновляются онлайн.
- [ ] E2E тест (mock feed → MarketRegime → StrategySelection → Risk → Execution) зелёный.
- [ ] Risk-governor блокирует торговлю при достижении лимитов (max_daily_loss, kill_switch_drawdown_72h).
- [ ] Research pipeline обеспечивает champion/challenger гейты и sandbox-изоляцию.
- [ ] README, DEV_SETUP, RUNBOOK, TODO обновлены по итогам paper-прогона.
