# Research champion/challenger гейты

## Минимальные требования кандидата
- PF in-sample ≥ 1.3, out-of-sample ≥ 1.1.
- Sharpe ≥ 1.0 (IS), ≥ 0.8 (OOS).
- MaxDD кандидата ≤ 1.3 × средний портфельный DD.
- N_trades ≥ 200, учтены комиссии и проскальзывание.
- Монте-Карло: p95 DD ≤ 4%, p95 PF ≥ 0.95.
- Корреляция с текущим портфелем ≤ 0.4.

## Процесс допуска
1. `generate_candidate` → формирование JSON описания стратегии (sandbox).
2. `run_backtest` → базовый отчёт (PF, Sharpe, DD, trades).
3. `run_walkforward` → устойчивость на разделах (PF, Sharpe, DD).
4. `run_montecarlo` → стресс с перемешиванием сделок/сллипеджа.
5. Чек лист QC (reports/04) → ручная верификация логов, отсутствие look-ahead.
6. Champion: промо в paper через feature flag (`enable_map.yaml`), наблюдение ≥ 7 дней.
7. Challenger: параллельный мониторинг; при деградации champion — автоматический свитч.

### Текущее состояние
- Заготовлен модуль `research_lab/backtests/vectorbt_runner.py` (чтение CSV и заглушка пакетного бэктеста).
- В `research_lab/pipeline_ci/champion_gate.py` описаны пороговые значения (`ChampionCriteria`) и функция `passes_gate`.
- Следующий шаг (PROMPT #4): интеграция фактических backtests (vectorbt), walk-forward и Monte-Carlo на базе DAO/Parquet историй.

## Безопасность
- ResearchAgent и инструменты работают в sandbox, без доступа к биржам/ключам.
- Все результаты экспортируются в telemetry + CSV (`research_lab/results.csv`) для аудита.

## Shadow-режим
- Файл кандидатов (`CHALLENGER_CONFIG`) поддерживает JSON/CSV с полями `id`, `strategy` и параметрами конфигурации стратегии.
- `research_lab/backtests/vectorbt_runner.py` загружает кандидатов и сохраняет результаты (PF, MaxDD, trades) через `save_results`.
- При запуске runner challengers подключаются в режиме тени; решения попадают в `reports/run_<RUN_ID>/shadow/*.csv` и продублированы в Parquet.
- Метрики safe-mode для challengers не влияют на champion и используются для отчётности/отбора.
