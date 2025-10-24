# TODO backlog

## must
- Провести 60-мин и 24h paper-прогоны с новыми параметрами, выгрузить отчёты (`reports/run_*/`), обновить Acceptance.
- Автоматизировать safe-mode: rolling корреляции + алерты (Grafana, Prometheus, RUNBOOK).
- Включить research pipeline (vectorbt_runner + champion_gate) в CI и формализовать артефакты.

## should
- Настроить автоматическую очистку/архивацию SQLite + алерты по размеру базы.
- Расширить telemetry/Grafana (latency buckets, equity curve, safe-mode панели) и описать реагирование в RUNBOOK.
- Подготовить CLI/management-команды для failover feed и пересчёта корреляций.

## nice
- Добавить PatternDiscovery/RedTeam/SelfCritique агенты (research расширения).
- Подготовить CLI для исследовательских сценариев (champion генерации).
- Генерация отчётов в PDF (Prometheus + Grafana snapshot).
