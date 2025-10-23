# План исполнения (7 дней до MVP paper)

## День 1–2
- Финализировать telemetry (Prometheus exporter, Grafana, stage latency, performance метрики).
- Провести paper-прогон ≥30 минут, подтвердить стабильность feed_health и safe-mode.
- Обновить документацию (DEV_SETUP, RUNBOOK, README) и конфиги символов.

## День 3
- Расширить тесты: мок фида, portfolio controller, risk сценарии; вытащить coverage ≥50%.
- Подготовить baseline CI (pytest + ruff + mypy) через GitHub Actions.
- Настроить автоматический экспорт `reports/telemetry_events.csv` в артефакт пайплайна.

## День 4
- Интегрировать реальные paper-данные (sandbox ключи), проверка на нескольких символах.
- Добавить оркестрационные хуки (safe_mode алерт, daily lock notification).
- Начать сбор исторических корреляций (research_lab/pipeline_ci, подготовка данных).

## День 5–6
- Подготовить champion/challenger pipeline: проверка PF/Sharpe, walk-forward, Monte-Carlo (заполнение reports/04/09).
- Развернуть наблюдение за экспозициями (net/gross) и связать с RUNBOOK (алерты и действия).
- Внедрить pre-trade sanity checks (liq/spread) на уровне ExecutionAgent + telemetry.

## День 7
- Полный 24h paper-прогон с сохранением метрик и логов.
- Анализ результатов, обновление Acceptance checklist (`reports/02`) и summary.
- Подготовка к canary: мок-планы ENSURE, freeze конфиги.
