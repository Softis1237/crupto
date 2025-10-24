# Аудит репозитория «crupto»

## 1. Карта проекта (актуальная структура)
- Корневые файлы: `README.md`, `requirements.txt`, `.env.example`, `CHANGELOG.md`, `ТЗ.txt`, `Инструкция Codex.txt`, `Новые идеи.txt`, `TODO.md`.
- Точки входа: `prod_core/runner.py`, скрипты `scripts/run_paper.sh`, `scripts/run_live.sh` (заглушка, запрещает live).
- Основные каталоги:

```text
.
├── prod_core/
│   ├── data/{feed.py, features.py}
│   ├── indicators/tech.py
│   ├── strategies/{base.py, breakout_4h.py, vol_exp_15m.py, range_rev_5m.py, funding_rev.py}
│   ├── risk/{engine.py, governor.py}
│   ├── exec/{broker_ccxt.py, portfolio.py}
│   ├── monitor/{logger.py, telemetry.py}
│   ├── configs/loader.py
│   └── runner.py
├── brain_orchestrator/{brain.py, regimes.py, validators.py, agents/, tools/}
├── tools/ (capabilities по агентам)
├── configs/{governance.yaml, enable_map.yaml, symbols.yaml}
├── dashboards/grafana/ (README_GRAFANA.md)
├── docs/{DEV_SETUP.md, RUNBOOK.md}
├── reports/00_repo_audit.md, 01–09_*.md, summary_latest.md
├── research_lab/ (dsl/, generators/, pipeline_ci/, tests/, backtests/)
├── scripts/{run_paper.sh, run_live.sh}
├── tests/*.py
└── .vscode/settings.json
```

## 2. Сопоставление с требованиями ТЗ
- Реализован CCXT ws+REST feed с backfill и контролем дрейфа (MarketDataFeed) + оркестратор runner с Prometheus экспортёром.
- Persist слой: SQLite DAO (`storage/crupto.db`), Parquet sink, автоматический экспорт `scripts/run_paper_60m.sh` → `reports/run_*/`.
- PortfolioController расширен (safe-mode, экспозиции, корреляции) и интегрирован в RiskManagerAgent/ExecutionAgent.
- Telemetry обновлена: equity, экспозиции, safe-mode, stage latency, Prometheus dashboard (datasource + dashboard.json).
- Тестовый каркас пополнен (`tests/test_persist_dao.py`, `test_portfolio_limits.py`, обновлён `test_risk_engine.py`). CI workflow (`.github/workflows/ci.yml`) добавлен.
- Research skeleton: `vectorbt_runner.py` и `champion_gate.py` заготовлены, отчёты 03/05/06/09/DEV/RUNBOOK обновлены.
- Каркас prod_core/brain_orchestrator/tools соответствует структуре из ТЗ: реализованы стратегии, RiskEngine, Governor, Portfolio controller, Telemetry exporter и реестр инструментов.
- Конфиги и Pydantic-валидаторы (`prod_core/configs/loader.py`) покрывают `governance.yaml`, `enable_map.yaml`, `symbols.yaml`.
- Тестовый каркас присутствует (`tests/test_feed_integrity.py`, `test_features_no_lookahead.py`, `test_governor.py`, `test_risk_engine.py`, `test_indicators.py`).
- Документация и отчёты 00–09 созданы, scripts и README/DEV_SETUP/RUNBOOK соответствуют требованиям paper-режима.
- Несоответствия остаются в частях реального фида, телеметрии, портфельных ограничений и дашбордов (см. ниже).

## 3. Несоответствия и пробелы
- Не покрыт интеграционный тест полного пайплайна (mock CCXT + плавающий runner); требуется 60/24h paper прогон и проверка gap-policy на реальных данных.
- Portfolio safe-mode пока опирается на эвристики — нужны проверки на исторических корреляциях и синхронизация с конфигами (`correlation_window_bars`, `correlation_refresh_seconds`).
- Research pipeline остаётся заглушкой: отсутствуют реальные backtests/walk-forward/MC и автоматизированные артефакты champion/challenger.
- Отсутствует автоматическая очистка/архивация SQLite и мониторинг размера БД (риск переполнения/деградации).
- Требуется довести тестовое покрытие ≥70% (feed, execution, governance) и убедиться, что CI выполняет ruff/mypy/pytest/coverage без ошибок.

## 4. Риски и блокеры
- Без реального 60+ минутного paper-теста с Parquet-выгрузками не подтверждены SLA фида и риск-контуры.
- Возможные расхождения метрик при переключении safe-mode/корреляций без интеграции с реальными данными.
- Research поток не даёт гарантий качества стратегий (champion/challenger) — риск false-positive допуска.
- CI добавлен, но пока не запускался (нужна проверка GitHub Actions либо локальное воспроизведение).

## 5. Быстрые фиксы (приоритет на ближайшие 48 ч)
1. Провести 60-минутный paper-прогон (`scripts/run_paper_60m.sh`), зафиксировать отчёты `reports/run_*/` и обновить Acceptance (reports/02).
2. Добавить интеграционный тест пайплайна (mock feed → strategy → execution) и измерить покрытие (`pytest --cov`).
3. Настроить/проверить CI (ruff/mypy/pytest/coverage) + загрузку артефактов на GitHub Actions.
4. Расширить telemetry/grafana для реальных статусов (latency buckets, equity curve) и документировать процедуры в RUNBOOK.
5. Подготовить шаги research pipeline: связать `vectorbt_runner` с реальными backtests, определить формат артефактов для champion_gate.

