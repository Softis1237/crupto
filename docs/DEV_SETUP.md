# DEV_SETUP

## Требования
- Python 3.13.x
- `pipx` или `uv` (рекомендуется), альтернативно `pip-tools`
- Docker (для Prometheus + Grafana)
- Git

## Настройка окружения

### Windows (PowerShell)
```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

### Linux / macOS
```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
cp .env.example .env
```

Опционально можно синхронизировать зависимости через `uv`:
```bash
uv sync
```

## Проверка окружения
```bash
pytest --maxfail=1 --disable-warnings -q
pytest --cov=prod_core --cov=brain_orchestrator --cov=tools --cov-report=term-missing
ruff check .
mypy .
```

## Prometheus + Grafana
1. Убедитесь, что ~/.config/grafana (или каталог конфигурации) содержит `dashboards/grafana/datasources.yml` и `dashboard.json`. Можно смонтировать директорию `dashboards/grafана` в контейнер.
2. Запустите стек (пример docker-compose):
   ```bash
   docker compose up prometheus grafana
   ```
   либо вручную: `docker run --net=host prom/prometheus`, `docker run --net=host grafana/grafana`.
3. В Prometheus добавьте таргет `http://localhost:9108/metrics` (port задаётся переменной `PROMETHEUS_PORT`).
4. В Grafana импортируйте `dashboards/grafana/dashboard.json` и выберите datasource `Prometheus`.

## Запуск пайплайна
```bash
MODE=paper scripts/run_paper.sh
# локальный smoke-тест (mock feed):
python -m prod_core.runner --max-seconds 180 --skip-feed-check --use-mock-feed
# реальный paper-run (60 мин):
python -m prod_core.runner --max-seconds 3600 --skip-feed-check
```

PowerShell без bash:
```powershell
$env:MODE = 'paper'
python -m prod_core.runner
# короткий тест (mock feed):
# $env:MODE = 'paper'; python -m prod_core.runner --max-seconds 180 --skip-feed-check --use-mock-feed
```

Параметры в `.env`:
- `PROMETHEUS_PORT` (по умолчанию 9108)
- `EXCHANGE`, `EXCHANGE_API_KEY`, `EXCHANGE_API_SECRET` (sandbox)
- `OPENAI_API_KEY` — опционально для исследовательских агентов.

## Pre-commit / статический анализ
```bash
pip install pre-commit
pre-commit install
ruff check .
mypy .
pytest --maxfail=1 --disable-warnings -q
pytest --cov=prod_core --cov=brain_orchestrator --cov=tools --cov-report=term-missing
```

## Полезные команды
- `scripts/run_paper.sh` — запуск пайплайна (автоматически устанавливает MODE=paper).
- `scripts/run_paper_60m.sh` — 60-минутный прогон с логами и выгрузкой Parquet/summary в `reports/run_*/`.
- `scripts/run_paper_24h.sh` — суточный paper-run (использует флаг `--max-seconds 86400`, перезапускается после фейла).
- `scripts/run_live.sh` — заглушка, предупреждает и завершает выполнение.
- `scripts/cleanup.py` — удаляет устаревшие `reports/run_*`, логи и `__pycache__` (по умолчанию держит 2 рана, 5 логов).
- `scripts/vacuum_and_rotate.py` — выгружает старые run_id из SQLite в Parquet и выполняет VACUUM (ротация БД).
- pytest tests/test_integration_pipeline.py -q — интеграционный smoke-тест runner'а с mock feed.
- python - <<'PY' ... (см. reports/09_research_gate.md) — запуск research pipeline (run_backtests > select_champions).

