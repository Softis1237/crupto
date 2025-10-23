# crupto — мультиагентный крипто-автотрейдинг (paper)

## Описание
Детерминированное ядро (`prod_core`) + мультиагентный оркестратор (`brain_orchestrator`) для безопасного paper-режима. LLM-слой занимается оркестрацией/аналитикой; риск, портфель и исполнение строго детерминированы.

## Структура
- `prod_core/` — feed (CCXT ws+REST) → features → regime → strategies → risk → exec → monitor.
- `brain_orchestrator/` — агенты, ToolRegistry, этапы пайплайна.
- `tools/` — инструменты, сгруппированные по агентам (capabilities).
- `configs/` — YAML (`governance`, `enable_map`, `symbols`) + валидаторы Pydantic.
- `dashboards/` — Prometheus exporter helper + Grafana (`datasources.yml`, `dashboard.json`).
- `docs/`, `reports/` — операционные инструкции, планы и чек-листы.
- `scripts/` — запуск paper (`run_paper.sh`), 60-минутный прогон (`run_paper_60m.sh`), live-заглушка.
- `tests/` — проверка фида, индикаторов, risk-engine, portfolio control, интеграционный цикл `_run_paper_loop`.

## Быстрый старт (Python 3.13)
1. Убедитесь, что Python 3.13.x установлен (Windows: py -3.13 --version, Linux/macOS: python3.13 --version).
2. Создайте virtualenv и установите зависимости:

   **Windows (PowerShell)**
   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   Copy-Item .env.example .env
   ```

   **Linux / macOS**
   ```bash
   python3.13 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   cp .env.example .env
   ```

3. Запустите тесты и линтеры для проверки окружения:
   ```bash
   pytest --maxfail=1 --disable-warnings -q
   pytest --cov=prod_core --cov=brain_orchestrator --cov=tools --cov-report=term-missing
   ruff check .
   mypy .
   ```

4. Запустите paper-runner в sandbox-режиме:
   ```bash
   MODE=paper scripts/run_paper.sh
   ```
   *Локальный smoke-тест*: `.venv/Scripts/python -m prod_core.runner --max-seconds 180 --skip-feed-check --use-mock-feed` (MODE=paper).
## Мониторинг и метрики
- Prometheus endpoint: `http://localhost:${PROMETHEUS_PORT:-9108}/metrics` (поднимается runner'ом через `dashboards.exporter.serve_prometheus`).
- Grafana: импортируйте `dashboards/grafana/datasources.yml` и `dashboard.json` (панели: Node Graph, Feed & Risk States, Stage Latency, Performance).
- Ключевые метрики: `equity_usd`, `pnl_cum_r`, `max_dd_r`, `feed_health`, `portfolio_safe_mode`, `stage_latency_ms`, `open_positions_count`, `exposure_gross_pct`, `execution_slippage_ratio`, `execution_reject_rate`.
- Все телеметрические события дублируются в `reports/telemetry_events.csv` и `storage/crupto.db`. Экспорт Parquet/CSV осуществляется `scripts/run_paper_60m.sh` → `reports/run_*/`.

## Конфиги и безопасность
- Валидация: `python -c "from prod_core.configs import ConfigLoader; ConfigLoader().load_governance(); ConfigLoader().load_symbols()"`.
- `MODE=live` запрещён до Acceptance; портфельные лимиты и safe-mode реализованы в `PortfolioController`.
- Секреты только через `.env`, не логируются и не коммитятся.

## Тесты и анализ
```bash
pytest --maxfail=1 --disable-warnings -q
pytest --cov=prod_core --cov=brain_orchestrator --cov=tools --cov-report=term-missing
ruff check .
mypy .
```

## Acceptance
Следуйте чек-листу `reports/02_acceptance_checklist.md`: ≥70% покрытия, 24h стабильного paper-запуска, kill-switch/daily-lock, Grafana с необходимыми метриками, обновлённые отчёты (`reports/summary_latest.md`).
