# crupto — мультиагентный крипто-автотрейдинг (paper)

## Описание
Детерминированное ядро (`prod_core`) + мультиагентный оркестратор (`brain_orchestrator`) для безопасного paper-режима. LLM-слой занимается оркестрацией/аналитикой; риск, портфель и исполнение строго детерминированы.

## Структура
- `prod_core/` — feed (CCXT ws+REST) → features → regime → strategies → risk → exec → monitor.
- `brain_orchestrator/` — агенты, ToolRegistry, этапы пайплайна.
- `tools/` — инструменты, сгруппированные по агентам (capabilities).
- `configs/` — YAML (`governance`, `enable_map`, `symbols`) + валидаторы Pydantic.
- `research_lab/` — backtests (vectorbt_runner), CI champion-gate, результаты исследовательских пайплайнов.
- `dashboards/` — Prometheus exporter helper + Grafana (`datasources.yml`, `dashboard.json`).
- `docs/`, `reports/` — операционные инструкции, планы и чек-листы.
- `scripts/` — запуск paper (`run_paper.sh`), 60-минутный прогон (`run_paper_60m.sh`), 24h-run (`run_paper_24h.sh`, `run_paper_24h.ps1`), live-заглушка.
- `tests/` — проверка фида, индикаторов, risk-engine, portfolio control, интеграционный цикл `_run_paper_loop`, vectorbt pipeline и champion gate.

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

После копирования `.env` включите виртуальную торговлю для тестов: установите `USE_VIRTUAL_TRADING=true`, `VIRTUAL_ASSET=VST`, `VIRTUAL_EQUITY=10000`. Пользовательские значения можно вынести в `.env.local`, чтобы не коммитить секреты.

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
   Для длительных прогонов с виртуальным балансом используйте скрипт `scripts/run_paper_vst.sh` — он запускает 8-часовой цикл, сохраняет логи и формирует отчёт в `reports/run_<RUN_ID>/virtual_summary.md`.

## Виртуальная торговля (VST)
- Флаг `USE_VIRTUAL_TRADING=true` включает sandbox-режим: CCXTBroker помечает ордера `virtual_asset`, а `PortfolioController` использует `VIRTUAL_EQUITY` в расчётах.
- Модуль `prod_core/exchanges/bingx_virtual.py` выполняет тестовый цикл VST/USDT и задействован в интеграционном тесте `tests/test_bingx_virtual_trade.py`, который не требует подключения к бирже.
- Для ручных сценариев вызывайте `run_virtual_vst_cycle` или `scripts/run_paper_vst.sh` — сделки сохраняются в SQLite, а Markdown-отчёт создаётся автоматически.
- Задавайте `RUN_ID` перед запуском (скрипт делает это сам), чтобы быстро извлекать ордера и trades из БД.
## Мониторинг и метрики
- Prometheus endpoint: `http://localhost:${PROMETHEUS_PORT:-9108}/metrics` (поднимается runner'ом через `dashboards.exporter.serve_prometheus`).
- Grafana: импортируйте `dashboards/grafana/datasources.yml` и `dashboard.json` (панели: Node Graph, Feed & Risk States, Stage Latency, Performance). Настройте datasource на локальную SQLite (`storage/crupto.db`) и Prometheus (`http://localhost:${PROMETHEUS_PORT}`), включите auto-refresh ≥10 с и создайте отдельную папку для VST-прогонов.
- Ключевые метрики: `equity_usd`, `pnl_cum_r`, `max_dd_r`, `feed_health`, `portfolio_safe_mode`, `stage_latency_ms`, `open_positions_count`, `exposure_gross_pct`, `execution_slippage_ratio`, `execution_reject_rate`.
- Все телеметрические события дублируются в `reports/telemetry_events.csv` и `storage/crupto.db`. Экспорт Parquet/CSV осуществляется `scripts/run_paper_60m.sh` → `reports/run_*/`.

## Конфиги и безопасность
- Валидация: `python -c "from prod_core.configs import ConfigLoader; ConfigLoader().load_governance(); ConfigLoader().load_symbols()"`.
- `MODE=live` запрещён до Acceptance; портфельные лимиты и safe-mode реализованы в `PortfolioController`.
- Секреты только через `.env`, не логируются и не коммитятся.

## Безопасность API-ключей
- Заводите ключи с IP-ограничениями и правами только на чтение/виртуальную торговлю; реальные ключи подключайте после Acceptance.
- Храните `.env` вне репозитория (например, `~/.config/crupto/.env`) и ссылкуйте его через `.env.local`; не коммитьте рабочие секреты.
- Для автоматических прогонов используйте менеджеры секретов (GitHub Actions secrets, Vault) и ограничивайте область действия сервисных аккаунтов.
- Периодически ревокуйте неиспользуемые ключи и проверяйте журналы биржи на аномальные входы.

## Тесты и анализ
```bash
pytest --maxfail=1 --disable-warnings -q
pytest --cov=prod_core --cov=brain_orchestrator --cov=tools --cov-report=term-missing
ruff check .
mypy .
```

## Acceptance
Следуйте чек-листу `reports/02_acceptance_checklist.md`: ≥70% покрытия, 24h стабильного paper-запуска, kill-switch/daily-lock, Grafana с необходимыми метриками, обновлённые отчёты (`reports/summary_latest.md`).
## Research pipeline
- `python research_lab/backtests/vectorbt_runner.py --config configs/strategy_candidates.json --start 2024-01-01 --end 2024-04-01 --csv-root data/history --save-csv research_lab/results/backtests.csv --save-json research_lab/results/backtests.json`
- `research_lab/pipeline_ci/champion_gate.py` → `select_champions` (порог PF IS/OOS, MaxDD, trades, corr).
- После допуска champions обновляйте `configs/enable_map.yaml` и публикуйте отчёт (`reports/09_research_gate.md`).
