# TODO backlog

## must
- Провести 60-мин и 24ч paper-прогоны, зафиксировать отчёты (`reports/run_*/`) и обновить Acceptance.
- Довести тестовое покрытие ≥70% (добавить интеграционный пайплайн-тест, расширить governance/execution) и убедиться, что CI зелёный.
- Формализовать research pipeline: связать `vectorbt_runner` с настоящими backtests, описать артефакты для `champion_gate`.

## should
- Настроить автоматическую очистку/архивацию SQLite + алерты по размеру базы.
- Расширить telemetry/grafana (latency buckets, equity curve, safe-mode алерты) и описать реагирование в RUNBOOK.
- Подготовить CLI/management-команды для failover feed и пересчёта корреляций.

## nice
- Добавить PatternDiscovery/RedTeam/SelfCritique агенты (research расширения).
- Подготовить CLI для исследовательских сценариев (champion генерации).
- Генерация отчётов в PDF (Prometheus + Grafana snapshot).
