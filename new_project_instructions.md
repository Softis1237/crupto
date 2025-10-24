# Инструкция для Codex по реализации и поддержке проекта

Этот документ адресован **Codex (AI‑помощнику)**, который будет использоваться в VS Code для разработки и сопровождения проекта. Инструкция задаёт стиль кода, порядок действий, требования к тестам, документации и мониторингу.  

## 1. Общие правила

1. **Язык**: все комментарии, названия переменных, сообщения журналов и документация пишутся **на русском языке**, используя лаконичные формулировки.  
2. **Стиль кода**: соблюдайте PEP 8, используйте типизацию `typing`. В методах и функциях пишите docstring, в котором коротко описана цель и аргументы.  
3. **Модулярность**: каждый компонент должен быть отделён: стратегии не знают о риске, risk engine не знает о брокере, агенты вызывают инструменты через реестр.  
4. **Безопасность**: не изменяйте `governance.yaml` и жёсткие лимиты в рантайме. Любые изменения риск‑политики должны производиться человеком через pull request.  
5. **Paper‑режим**: пока проект не прошёл Acceptance, **не допускайте перехода в live‑режим**. Проверки в `prod_core/runner.py` должны выбрасывать исключение при `MODE=live`. Все тесты и интеграции запускайте с `USE_VIRTUAL_TRADING=true` и меткой виртуального актива (`VIRTUAL_ASSET=VST`).  
6. **Без телеграм‑ботов**: в проекте не используется Telegram. Уведомления о состоянии выполняются через логи и Prometheus/Grafana.  
7. **Документация**: при добавлении нового файла или функции обновляйте `README.md`, `SPEC.md` и файлы в `reports/`. Составляйте краткие отчёты на русском.  

## 2. Шаги по созданию модулей

Ниже приведён ориентировочный порядок работы. Каждому шагу соответствует **prompts** в SPEC.md, но здесь перечислены ключевые действия.

### 2.1 Создание структуры

- Сгенерируйте папки и пустые файлы согласно структуре в SPEC. Создайте `requirements.txt`, `.env.example`, `scripts/run_paper.sh`, `scripts/run_paper_vst.sh` и `scripts/run_live.sh`.  
- Напишите `README.md` с краткой инструкцией по установке (pip install -r requirements.txt), настройке `.env` и запуску paper‑режима.

### 2.2 Реализация ядра `prod_core`

- **Feed и Features**: напишите класс `DataFeed` в `prod_core/data/feed.py`, который обеспечивает загрузку свечей и funding через CCXT (либо через mock‑фид). В `features.py` реализуйте функции ATR, ADX, BB, RSI, квантиль волатильности и наклон EMA200.  
- **Стратегии**: реализуйте базовый класс `TradingStrategy` в `prod_core/strategies/base.py`. Добавьте 4 стратегии: `breakout_4h.py`, `vol_exp_15m.py`, `range_rev_5m.py`, `funding_rev.py`. Убедитесь, что каждая стратегия возвращает список объектов `StrategySignal` с полями `side`, `entry`, `confidence`.  
- **RiskEngine**: реализуйте класс в `prod_core/risk/engine.py` так, чтобы он соответствовал последнему SPEC (RiskSettings, RiskState, методы `risk_budget_pct`, `size_position` и dynamic reduction).  
- **PortfolioController**: реализуйте в `prod_core/exec/portfolio.py`, обеспечьте safe‑mode, контроль корреляций, регистрацию/проверку позиций, обновление equity.  
- **Exec**: реализуйте брокера (`broker_ccxt.py`) для выставления ордеров через CCXT (функции place_order/cancel_all), методы для расчёта проскальзывания и проверки ликвидности. Поддержите sandbox-метки (`virtual_asset`) и избегайте синхронных HTTP-вызовов в async-коде (используйте `aiohttp` или `ccxt.async_support`).  
- **Monitor**: в `prod_core/monitor` реализуйте `TelemetryExporter`, Prometheus exporter, логи (loguru), запись equity/trades в SQLite.  
- **Runner**: напишите `prod_core/runner.py` с CLI‑аргументами, инициализацией PersistDAO, TelemetryExporter, Prometheus, загрузкой стратегий, RiskEngine, PortfolioController и BrainOrchestrator. Поддержите флаги `--max-seconds`, `--max-cycles`, `--skip-feed-check`, `--use-mock-feed`.  

### 2.3 Реализация слоя агентов `brain_orchestrator`

- **BaseTool**: в `tools/base.py` определите `ToolSpec`, `ToolContext` и протокол `BaseTool`.  
- **ToolRegistry**: создайте модуль, который регистрирует инструменты и разрешает `resolve()` по capability.  
- **Агенты**: напишите классы в `agents/`: `MarketRegimeAgent`, `StrategySelectionAgent`, `RiskManagerAgent`, `ExecutionAgent`, `MonitorAgent`. Каждый агент должен иметь метод `run()`/`tick()`, принимать context и использовать инструменты через registry.  
- **Regimes**: в `regimes.py` определите функции/классы для классификации режима рынка.  
- **BrainOrchestrator**: в `brain.py` реализуйте оркестратор: цикл `run_cycle()` должен получать новые свечи, вычислять features, режим, запускать агентов, собирать планы, передавать их в RiskManager и Execution, обновлять мониторинг.  

### 2.4 Инструменты (`tools`)

- Создайте файлы в `tools/tools_strategy_selection_agent/`: `strategy_scorer.py`, `cooldown_manager.py`, реализовав простой скоринг и управление cooldown.  
- Создайте файлы в `tools/tools_risk_manager_agent/`: `dd_guard.py`, `position_sizer.py`, `stop_planner.py`, реализовав логику ограждения по drawdown, масштабирования по уверенности и выставления стопов.  
- Реализуйте `tools/tools_execution_agent/` (например, `liquidity_check.py`, `slippage_estimator.py`, `place_order.py`) — упростите по возможности, но следите за тем, чтобы всегда проверять ликвидность, учитывать проскальзывание, дробить крупные заявки и возвращать идентификатор ордера.  
- Добавьте инструмент `export_metrics` в монитор — экспортирует метрики агентов и стратегий в Prometheus.  

### 2.5 Configs и проверка

- Заполните `prod_core/configs/governance.yaml` базовыми лимитами, затем защитите их от изменения (в коде не должно быть записи).  
- Заполните `prod_core/configs/enable_map.yaml` со списком стратегий в каждом режиме (`trend_up`, `trend_down`, `range_lowvol`, `range_highvol`, `panic`). Добавьте параметры hysteresis (min_bars_hold), cooldown_after_2_losses.  
- Напишите `prod_core/configs/symbols.yaml` для выбранных активов (например, `BTCUSDT` и `ETHUSDT`), с таймфреймами [1m, 5m, 15m, 1h, 4h], `poll_interval_seconds`, `backfill_bars` и т. д.  
- Создайте модуль `brain_orchestrator/validators.py` для валидации YAML‑конфигов и типов. Вызовите его из runner при загрузке.  

### 2.6 Telemetry, Prometheus и Grafana

- В `dashboards/exporter.py` запустите сервер на порту из `PROMETHEUS_PORT` и реализуйте эндпоинты `/metrics` и `/graph`.  
- В `/metrics` экспортируйте: 
  - `agent_state{agent="brain"}` — 1=OK, 0=ERR, 2=WARN;  
  - `strategy_active{strategy="breakout_4h"}` — 1/0;  
  - `regime_label` (integer gauge);  
  - `pnl_total`, `drawdown_pct`, `risk_cap_pct`, `slippage_bps` и др.;  
  - `tool_calls_total{tool="..."}` и `tool_latency_ms{tool="..."}` (histogram/summary).  
- В `/graph` верните JSON вида `{ "nodes": [{"id": "brain", "state": "ok"}, ...], "edges": [{"source": "regime", "target": "strategy", "active": true}, ...] }`. Обновляйте поле `active` для каждой стрелки при последнем вызове.  
- В `dashboards/grafana` создайте JSON‑дашборды: `dashboard_nodes.json` (node‑graph) и `dashboard_ops.json` (PnL, DD, слоты времени, число активных стратегий).  
- Опишите в `dashboards/grafana/datasource_prometheus.md` как импортировать dashboards в Grafana.  

### 2.7 Research pipeline

- В `research_lab/dsl/` разработайте простую DSL/JSON схему для описания стратегий (индикаторы, правила входа/выхода, параметры).  
- В `research_lab/generators/` напишите скрипт, который при помощи LLM (OpenAI) генерирует кандидаты стратегий, сохраняя описание и параметризацию в DSL.  
- В `research_lab/backtests/` реализуйте Jupyter‑ноутбук и/или Python‑скрипт для бэктеста через `vectorbt`: загружает данные, прогоняет стратегию, рассчитывает PF, MaxDD, Sharpe, expectancy, capacity (учитывая спреды/комиссии).  
- В `research_lab/pipeline_ci/` опишите **gate_spec.md**: условия допуска (PF≥1.2, MaxDD≤1.3×допустимого, средняя частота сделок в рамках ликвидности, низкая корреляция с существующими стратегиями, положительное ожидание). Реализуйте CI‑скрипт, который прогоняет кандидата по этим гейтам и, если все условия выполнены, формирует PR на обновление `enable_map.yaml`.  

### 2.8 Тестирование

- Напишите юнит‑тесты в папке `tests/`.  Минимальный набор: тесты RiskEngine (корректный расчёт риска и размера), PortfolioController (safe‑mode, лимиты, корреляции), стратегии (сигнал появляется, когда индикаторы выполняются), инструменты (корректно возвращают значения, уважают cooldown и drawdown guard), регистратор ToolRegistry (возвращает верные инструменты).  
- Напишите интеграционные тесты: поднять mock‑feed, прогнать paper‑loop 10 циклов, убедиться, что все метрики корректны, ордера выставляются, safe‑mode активируется, если требуется. Добавьте отдельный тест для виртуальной торговли (VST), который выполняет sandbox-цикл без внешнего подключения и проверяет метаданные в БД.  
- Покрытие должно быть ≥70 %. Используйте `pytest`, `pytest-cov`.  

## 3. Обновление и поддержка

1. **Изменения в коде**: после каждой итерации обновляйте `SPEC.md` и `README.md`, описывая новые функции, конфигурации, метрики.  
2. **Reports**: ведите файлы в `reports/`. После каждого спринта обновляйте `summary_latest.md`, `00_repo_audit.md`, `02_acceptance_checklist.md`. Отмечайте, что выполнено, что осталось.  
3. **Grafana dashboards**: при добавлении нового агента, инструмента или метрики обновляйте JSON‑дашборды.  
4. **Проверка конфигураций**: при каждой загрузке YAML используйте валидацию. Если файл некорректен, выбрасывайте исключение с объяснением.  
5. **Администрирование БД**: периодически очищайте таблицы equity/trades через cron или скрипт, архивируя исторические данные.  
6. **Эксперименты**: реализуйте новые стратегии сначала в `research_lab`, пройдите pipeline, затем, после прохождения всех гейтов, добавьте в `prod_core/strategies` и `enable_map.yaml`.  

## 4. Проверка прогресса

При проверке текущей реализации на GitHub:

- Сравнивайте фактическую структуру репозитория с пунктом 2 этого документа.  
- Убедитесь, что реализованы все модули: RiskEngine, PortfolioController, все стратегии, агенты, инструменты, мониторинг.  
- Проверяйте наличие Prometheus exporter и Grafana dashboards.  
- Сверяйте файлы `reports/00_repo_audit.md`, `reports/summary_latest.md` с чек‑листом acceptance.  
- Отмечайте, что уже сделано (risk‑движок, safe‑mode, mock‑feed, 79 % покрытия, простейший research pipeline).  
- Указывайте, что нужно улучшить (интеграционные тесты, champion/challenger pipeline, node graph, cleanup БД).  

Формулируйте обратную связь честно, с конкретикой: какой файл реализован хорошо, где код нужно улучшить (например, тестирование, документация, покрытия).  

## 5. Вывод

Следуя этой инструкции, Codex сможет помочь реализовать полноценную систему автотрейдинга: от получения данных и вычисления индикаторов до исполнения сделок, контроля риска, мониторинга и исследования новых стратегий.  
Проект должен оставаться в режиме *paper* до тех пор, пока не будут выполнены Acceptance критерии: ≥70 % покрытие тестами, 24‑часовой стабильный paper‑run, рабочая Grafana, успешное прохождение research pipeline.  Всё это необходимо, чтобы гарантировать безопасность и надёжность системы перед выходом на реальные торги и монетизацию.
