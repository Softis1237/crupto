# Асинхронная архитектура

## Модель
- Основа: `asyncio` событийный цикл + фоновые таски `MarketDataFeed` (`start`/`subscription_loop`).
- Runner (`_run_paper_loop`) запускает feed, ждёт readiness всех подписок, далее каждые `poll_interval_seconds` пробегает по символам/таймфреймам.
- Пайплайн `feed → features → regime → strategy → risk → execution → monitor` исполняется синхронно, но все стадии измеряют латентность и публикуют `stage_latency_seconds{stage}`.

## Синхронизация и очереди
- Feed поддерживает собственные кольцевые буферы и `asyncio.Lock` на каждый `symbol/timeframe` — данный слой выступает очередью данных.
- `last_processed[(symbol, timeframe)]` в runner предотвращает повторную обработку одного и того же бара.
- Дополнительные очереди не требуются, так как планирование выполняется быстрее, чем период таймфрейма.

## SLA и наблюдаемость
- Target latency: ≤250 мс на `market_regime`, ≤150 мс на `strategy_selection`, ≤200 мс на `risk_manager`; execution и мониторинг ≤500 мс.
- `stage_latency_seconds` + Grafana Bar Gauge визуализируют p95 (используется `histogram_quantile`).
- `feed_health` обновляется на каждом баре; деградация автоматически фиксируется и выводится в Status History.

## Расширение параллелизма
- При росте числа стратегий допускается вынесение `strategy_agent.run` в `asyncio.to_thread` либо `TaskGroup`.
- Сервисные агенты (research, мониторинг) могут запускаться в отдельных `asyncio.Task` с обменом через asyncio.Queue при дальнейшем развитии.
- Для graceful shutdown используется `stop_event` + обработка сигналов SIGINT/SIGTERM.
