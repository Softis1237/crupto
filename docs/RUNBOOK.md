# RUNBOOK (paper-режим)

## Старт
1. Заполнить `.env` (MODE=paper, sandbox API ключи, `PROMETHEUS_PORT`).
2. Проверить конфиги: `python -c "from prod_core.configs import ConfigLoader; ConfigLoader().load_governance(); ConfigLoader().load_symbols()"`.
3. Запустить Prometheus/Grafana (см. DEV_SETUP) и убедиться, что datasource Prometheus активен.
4. Запустить пайплайн: `scripts/run_paper.sh` (варианты: `scripts/run_paper_60m.sh` для 60-минутного окна или `scripts/run_paper_24h.sh` для суточного прогона с выгрузками). Скрипты работают и без GNU `timeout`: runner ограничивается аргументом `--max-seconds`.
5. В логе должно появиться сообщение о регистрации фида и старте Prometheus (`Prometheus exporter слушает порт ...`).

## Остановка
- Ctrl+C в терминале → runner ловит сигнал и завершает feed (`Paper-loop остановлен`).
- Убедиться, что `feed_health` вернулся в `-1` (paused) и нет активных планов.

## Мониторинг
- Prometheus endpoint: `http://localhost:9108/metrics`.
- Grafana:
  - **Agent Topology** (Node Graph) — состояние агентов/инструментов и ребёр.
  - **Feed & Risk States** (Status history) — `feed_health`, `daily_lock_state`, `dd_state`, `regime_label`.
  - **Stage Latency** (Bar gauge + histogram) — наблюдайте p95 по `stage_latency_ms`.
  - **Performance** (Timeseries) — `equity_usd`, `pnl_cum_r`, `max_dd_r`.
  - **Exposure & Positions** (stat-панели) — `open_positions_count`, `exposure_gross_pct`, `exposure_net_pct`, `portfolio_safe_mode`.
- Логи: stdout + `reports/telemetry_events.csv`.
- Для архива суточного прогона сделайте экспорт графика Grafana вручную (Share → Export) и приложите файл.

## Алерты и реакция
- `FeedHealthDegraded` — правило из `configs/prometheus/alerts.yml` (`avg_over_time(feed_health[30s]) < 0.5`). Действия: проверить CCXT/ws, перезапустить feed. Тест: запустить runner с `ALERT_TEST_FEED_HEALTH=bad` на 30 с.
- `DrawdownCritical` — `max_dd_r >= 1.5`. Действия: активировать kill-switch, проверить отчёты `reports/run_*/summary.md`. Тест: временно уменьшить лимиты или обновить DAO вручную.
- `DailyLockEngaged` — `daily_lock_state{reason!="limits_ok"} == 1`. Действия: посмотреть `$labels.reason`, провести ревью и снять блок только вручную. Тест: `ALERT_TEST_DAILY_LOCK=max_daily_loss`.
- `PortfolioSafeModeStuck` — `portfolio_safe_mode == 1` более 5 минут. Действия: проанализировать корреляции и лимиты. Тест: `ALERT_TEST_SAFE_MODE=on`.
- `RunnerHeartbeatLost` — `(time() - runner_last_cycle_ts > 90)` либо `absent` метрики. Действия: убедиться, что `prod_core.runner` работает, перезапустить процесс. Тест: остановить runner либо заморозить цикл.
- `MetricsDeadman` — `absent(feed_health)`. Действия: проверить Prometheus scraping и exporter, перезапустить процесс.
## Ротация данных
- Скрипт: python scripts/vacuum_and_rotate.py --db storage/crupto.db --out reports/archive.
- Параметры --keep-days (дней), --keep-runs (минимум последних run_id), есть режим --dry-run.
- Новые run_id остаются в SQLite, старые выгружаются в Parquet/CSV и удаляются, затем выполняется VACUUM.
- Перед ротацией убедитесь, что длительные запуски завершены и run_id архивированы с помощью export_run.

## Очистка артефактов
- После каждого paper-рана выполняйте `python scripts/cleanup.py` (по умолчанию хранит 2 последних каталога `reports/run_*` и 5 логов).
- При необходимости задайте `--keep-runs`/`--keep-logs`; для проверки используйте `--dry-run`.
- Убедитесь, что `storage/crupto.db`, `logs/` и временные csv/parquet не попадают в Git (см. `.gitignore`).
- Перед запуском нового цикла удалите старые run-директории, чтобы Grafana/отчёты ссылались только на актуальные артефакты.


Alertmanager конфиг-шаблон: `configs/alertmanager/config.sample.yml` (использует env `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). Правила Prometheus: `configs/prometheus/alerts.yml`.

Для локального теста без реального инцидента выставьте переменные перед запуском runner и дождитесь соответствующего интервала:
```powershell
$env:ALERT_TEST_FEED_HEALTH = 'bad'   # вернуть 1 — 'good'
$env:ALERT_TEST_DAILY_LOCK = 'max_daily_loss'
$env:ALERT_TEST_SAFE_MODE = 'on'     # 'off' чтобы сбросить
```
```bash
export ALERT_TEST_FEED_HEALTH=bad
export ALERT_TEST_DAILY_LOCK=max_daily_loss
export ALERT_TEST_SAFE_MODE=on
```
После проверки сбросьте переменные (`Remove-Item Env:ALERT_TEST_*` / `unset ALERT_TEST_*`).


## Инциденты и действия
- `feed_health=0` или резкий рост `execution_reject_rate` → перевести стратегии в hold, проверить соединение/лимиты.
- `daily_lock_state=1` или `dd_state <= -1.8` → стоп торговли, ручная проверка портфеля.
- `stage_latency_seconds` > SLA (бар красный) → проанализировать соответствующую стадию, проверить очереди feed.
- Safe-mode (`PortfolioController.safe_mode=True`) → сократить риск (обновить enable_map) и обновить корреляции.

## Отчётность
- Для 60-минутного теста используйте `scripts/run_paper_60m.sh`: результаты появятся в `reports/run_*/` (Parquet + CSV + summary.md + лог).
- По окончании сессии приложить скрин ключевых панелей Grafana и экспорт метрик (Prom → `curl http://localhost:9108/metrics`).
- Обновить `reports/summary_latest.md` и чек-лист Acceptance (`reports/02_acceptance_checklist.md`) со ссылкой на run ID.
