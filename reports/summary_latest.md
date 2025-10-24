# Итоговый отчёт (24.10.2025)

## Обзор
- Runner получил `--feed-timeout <сек>`: при отсутствии WebSocket подключений за X секунд фид переводится в REST-поллинг (`force_rest_mode`).
- Добавлен PowerShell-скрипт `scripts/run_paper_24h.ps1` (автоперезапуск, чистка старых `reports/run_*` после экспорта).
- Стратегии (breakout/range-reversion/vol-exp/funding) сделаны агрессивнее: снижены пороги, удержание ≤4 баров, что позволяет paper-режиму генерировать сделки без API-ключей.
- Safe-mode обновлён: порог корреляции 0.60, формула мультипликатора `1 - (corr - threshold)/(1 - threshold)` и документированная процедура реагирования.
- Research pipeline: `vectorbt_runner` подключён к vectorbt 0.28.1, `champion_gate` читает новые метрики (pf_is/pf_oos/max_dd/corr/trades). В `research_lab/results/` сохраняются CSV/JSON с примером запуска.
- CI (`.github/workflows/ci.yml`) ставит `requirements.txt`, выполняет smoke `python -m prod_core.runner --max-seconds 10 --skip-feed-check --use-mock-feed`, затем pytest+coverage и публикует `coverage.xml`.

## Создано / обновлено
- `prod_core/runner.py`, `prod_core/data/feed.py`, `prod_core/exec/broker_ccxt.py`: логика `--feed-timeout`, REST-фолбэка, симуляция заявок без ключей.
- Стратегии (`breakout_4h`, `range_rev_5m`, `vol_exp_15m`, `funding_rev`) — снижены пороги, `min_hold_bars` 2–4.
- `prod_core/exec/portfolio.py` — `max_abs_correlation=0.60`, новая формула мультипликатора и документация (`reports/06_portfolio_risk.md`).
- `scripts/run_paper_24h.ps1`, обновлён `scripts/run_paper_24h.sh`, README, docs/DEV_SETUP.md, docs/RUNBOOK.md (PowerShell и WSL сценарии, очистка перед 24h-run).
- `research_lab/backtests/vectorbt_runner.py`, `research_lab/pipeline_ci/champion_gate.py`, `configs/strategy_candidates.json`, `research_lab/results/backtests.{csv,json}` — рабочий research pipeline.
- Новые тесты: `tests/test_vectorbt_runner.py`, `tests/test_champion_gate.py`, `tests/test_broker_fallback.py`, `tests/test_runner_feed_timeout.py`, обновлён `tests/test_integration_pipeline.py` (mock-feed smoke).

## Прогон paper_test_observe (пример 3 мин, REST-backfill)
- Run ID: `paper_test_observe`; ордера 1, сделки 1, PnL_R = 0.0.
- Equity: 10 000 → 10 000 USD; метрики latency p95 (ms): market_regime 7.1, strategy_selection 2.0, risk_manager 3.9, execution 0.0, monitor 3.5.
- Артефакты (`reports/run_paper_test_observe/`): equity.csv, trades.csv, orders.csv, latency.csv, summary.md.

## Корреляции
- Rolling-window 60 min по данным BinanceUSDM (1m): corr(BTC, ETH) — median 0.86, max 0.88, 100% минут ≥ 0.60 → safe-mode multiplier срабатывает, снижая cap до ~0.20×. Требуется тщательный мониторинг алерта `PortfolioSafeModeStuck`.

## Риски
- Полноценные 60-минутный и 24-часовой paper-прогоны ещё предстоит провести с актуальными стратегиями (новые параметры требуют наблюдения ≥1 ч).
- Safe-mode зависит от ручного ротационного анализа корреляций; нужно автоматизировать выгрузку/репорт.
- Research pipeline пока запускается вручную (нет CI job/cron).

## Следующие шаги
1. Запустить 60m и 24h paper-run с новыми параметрами, дождаться сделок, обновить `reports/summary_latest.md` и `reports/02_acceptance_checklist.md`.
2. Завершить автоматизацию safe-mode алертов: rolling corr выгрузка + реакция (обновить RUNBOOK/alerts.yml).
3. Интегрировать research pipeline в CI (vectorbt backtests + champion_gate) и формализовать артефакты.
4. Подготовить long-run TODO: контроль размеров БД (`vacuum_and_rotate.py`), дополнительные Grafana панели и уведомления.
