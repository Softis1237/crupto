# TODO backlog

## must
- Провести 60-мин и 24ч paper-прогоны, зафиксировать отчёты (`reports/run_*/`) и обновить Acceptance.
- Запустить полный CI (ruff/mypy/pytest --cov) в GitHub Actions и удерживать покрытие ≥70%.
- Формализовать research pipeline: связать `vectorbt_runner` с настоящими backtests, описать артефакты для `champion_gate`.

## should
- Настроить автоматическую очистку/архивацию SQLite + алерты по размеру базы.
- Расширить telemetry/grafana (latency buckets, equity curve, safe-mode алерты) и описать реагирование в RUNBOOK.
- Настроить alert-правила на рост корреляций (PortfolioSafeModeStuck, corr > 0.65) и связать с уведомлениями.
- Подготовить CLI/management-команды для failover feed и пересчёта корреляций.

## nice
- Добавить PatternDiscovery/RedTeam/SelfCritique агенты (research расширения).
- Подготовить CLI для исследовательских сценариев (champion генерации).
- Генерация отчётов в PDF (Prometheus + Grafana snapshot).
