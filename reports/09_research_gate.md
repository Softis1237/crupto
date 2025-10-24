# Research champion/challenger гейты

## Минимальные требования к кандидату
- PF in-sample ≥ 1.3, out-of-sample ≥ 1.1  
- Sharpe ≥ 1.0 (IS), ≥ 0.8 (OOS)  
- MaxDD кандидата ≤ 1.3 × средний портфельный DD  
- N_trades ≥ 200 (с учётом комиссий и проскальзывания)  
- Монте-Карло: p95 DD ≤ 4 %, p95 PF ≥ 0.95  
- Корреляция с текущим портфелем ≤ 0.4

## Процесс допуска
1. `generate_candidate` → формируем JSON/CSV с параметрами стратегии (sandbox).
2. `vectorbt_runner` → расчёт PF, DD, corr, trades, Sharpe (IS/OOS).
3. `run_walkforward` → устойчивость на нескольких окнах (PF, Sharpe, DD).
4. `run_montecarlo` → стресс с перетасовкой сделок/слиппеджем.
5. QC-чеклист (`reports/04`) → ручная верификация логов и отсутствия look-ahead.
6. Champion: включение через `configs/enable_map.yaml`, наблюдение ≥ 7 дней.
7. Challenger: параллельный мониторинг; при деградации champion — автоматический свитч.

### Текущее состояние
- `research_lab/backtests/vectorbt_runner.py` интегрирован с vectorbt 0.28.1: загружает кандидатов, исторические цены (CCXT или локальный CSV) и считает PF (IS/OOS), MaxDD, corr, trades.  
  Команда CLI:

  ```bash
  python research_lab/backtests/vectorbt_runner.py \
    --config configs/strategy_candidates.json \
    --start 2024-01-01 --end 2024-04-01 \
    --csv-root data/history \
    --save-csv research_lab/results/backtests.csv \
    --save-json research_lab/results/backtests.json
  ```

  Поддерживаемые поля кандидата: `strategy`, `candidate_id`, `symbol`, `timeframe`, `source/csv_path`, параметры конфигов стратегий.

- `research_lab/pipeline_ci/champion_gate.py` читает CSV/JSON (`load_results`) и проверяет критерии через `passes_gate`/`select_champions` (PF IS/OOS, MaxDD, corr, trades).
- После утверждения champions обновляем `configs/enable_map.yaml` и подключаем challengers через переменную `CHALLENGER_CONFIG`.

### Как запускать pipeline (sandbox)
```bash
python - <<'PY'
from pathlib import Path
from research_lab.backtests.vectorbt_runner import run_backtests
from research_lab.pipeline_ci.champion_gate import select_champions

results = run_backtests(
    config_path="configs/strategy_candidates.json",
    start="2024-01-01",
    end="2024-03-01",
    csv_root=Path("data/history"),
    save_csv=Path("research_lab/results/backtests.csv"),
    save_json=Path("research_lab/results/backtests.json"),
)
champions = select_champions("research_lab/results/backtests.csv")
print([c.candidate_id for c in champions])
PY
```
- CSV/JSON отчёты храним в `research_lab/results/`.
- После допуска champions публикуем summary в #research и синхронизируем TODO/acceptance.

## Безопасность
- ResearchAgent и инструменты работают в sandbox без доступа к биржам и ключам.
- Все результаты экспортируются в telemetry + CSV/JSON (`research_lab/results/*.csv|json`) для аудита.

## Shadow-режим
- `CHALLENGER_CONFIG` (JSON/CSV) поддерживает поля `candidate_id`, `strategy`, параметры конфигурации.
- `vectorbt_runner.load_shadow_strategies` загружает кандидатов для подключения в runner (shadow execution).
- Метрики shadow записываются в `reports/run_<RUN_ID>/shadow/` и не влияют на действующего champion до завершения анализа.
