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
- `research_lab/backtests/vectorbt_runner.py` умеет загружать кандидатов (`load_candidates`) и выполнять пакетный бэктест (`run_backtests`, временная заглушка вместо vectorbt) с сохранением CSV/JSON.
- `research_lab/pipeline_ci/champion_gate.py` предоставляет `ChampionCriteria`, чтение результатов (`load_results`) и фильтрацию (`select_champions`, `passes_gate`) по порогам PF/DD/corr/trades.
- Следующий шаг — заменить заглушку на фактические vectorbt-стратегии + walk-forward/MC.

### Как запускать pipeline (sandbox)
```bash
python - <<'PY'
from pathlib import Path
from research_lab.backtests.vectorbt_runner import run_backtests
from research_lab.pipeline_ci.champion_gate import select_champions

results = run_backtests(
    "configs/strategy_candidates.yaml",
    start="2024-01-01",
    end="2024-03-01",
    save_csv=Path("research_lab/results/backtests.csv"),
    save_json=Path("research_lab/results/backtests.json"),
)
champions = select_champions("research_lab/results/backtests.csv")
print([c.candidate_id for c in champions])
PY
```
- CSV/JSON результаты кладём в `research_lab/results/`.
- После утверждения champions обновляем `configs/enable_map.yaml` и прокидываем challengers через `CHALLENGER_CONFIG`.

## Безопасность
- ResearchAgent и инструменты работают в sandbox, без доступа к биржам/ключам.
- Все результаты экспортируются в telemetry + CSV (`research_lab/results.csv`) для аудита.

## Shadow-режим
- Файл кандидатов (`CHALLENGER_CONFIG`) поддерживает JSON/CSV с полями `id`, `strategy` и параметрами конфигурации стратегии.
- `research_lab/backtests/vectorbt_runner.py` загружает кандидатов и сохраняет результаты (PF, MaxDD, trades) через `save_results`.
- При запуске runner challengers подключаются в режиме тени; решения попадают в `reports/run_<RUN_ID>/shadow/*.csv` и продублированы в Parquet.
- Метрики safe-mode для challengers не влияют на champion и используются для отчётности/отбора.
