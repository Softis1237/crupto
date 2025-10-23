# DEV_SETUP

## ����������
- Python 3.13.x
- `pipx` ��� `uv` (�������������), ������������� `pip-tools`
- Docker (��� Prometheus + Grafana)
- Git

## ��������� ���������

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

����������� ����� ���������������� ����������� ����� `uv`:
```bash
uv sync
```

## �������� ���������
```bash
pytest --maxfail=1 --disable-warnings -q
pytest --cov=prod_core --cov=brain_orchestrator --cov=tools --cov-report=term-missing
ruff check .
mypy .
```

## Prometheus + Grafana
1. ���������, ��� ~/.config/grafana (��� ������� ������������) �������� `dashboards/grafana/datasources.yml` � `dashboard.json`. ����� ������������ ���������� `dashboards/graf���` � ���������.
2. ��������� ���� (������ docker-compose):
   ```bash
   docker compose up prometheus grafana
   ```
   ���� �������: `docker run --net=host prom/prometheus`, `docker run --net=host grafana/grafana`.
3. � Prometheus �������� ������ `http://localhost:9108/metrics` (port ������� ���������� `PROMETHEUS_PORT`).
4. � Grafana ������������ `dashboards/grafana/dashboard.json` � �������� datasource `Prometheus`.

## ������ ���������
```bash
MODE=paper scripts/run_paper.sh
# ��������� smoke-���� (mock feed):
python -m prod_core.runner --max-seconds 180 --skip-feed-check --use-mock-feed
# �������� paper-run (60 ���):
python -m prod_core.runner --max-seconds 3600 --skip-feed-check
```

PowerShell ��� bash:
```powershell
$env:MODE = 'paper'
python -m prod_core.runner
# �������� ���� (mock feed):
# $env:MODE = 'paper'; python -m prod_core.runner --max-seconds 180 --skip-feed-check --use-mock-feed
```

��������� � `.env`:
- `PROMETHEUS_PORT` (�� ��������� 9108)
- `EXCHANGE`, `EXCHANGE_API_KEY`, `EXCHANGE_API_SECRET` (sandbox)
- `OPENAI_API_KEY` � ����������� ��� ����������������� �������.

## Pre-commit / ����������� ������
```bash
pip install pre-commit
pre-commit install
ruff check .
mypy .
pytest --maxfail=1 --disable-warnings -q
pytest --cov=prod_core --cov=brain_orchestrator --cov=tools --cov-report=term-missing
```

## �������� �������
- `scripts/run_paper.sh` � ������ ��������� (������������� ������������� MODE=paper).
- `scripts/run_paper_60m.sh` � 60-�������� ������ � ������ � ��������� Parquet/summary � `reports/run_*/`.
- `scripts/run_paper_24h.sh` � �������� paper-run (���������� ���� `--max-seconds 86400`, ��������������� ����� �����).
- `scripts/run_live.sh` � ��������, ������������� � ��������� ����������.
- `scripts/cleanup.py` � ������� ���������� `reports/run_*`, ���� � `__pycache__` (�� ��������� ������ 2 ����, 5 �����).
- `scripts/vacuum_and_rotate.py` � ��������� ������ run_id �� SQLite � Parquet � ��������� VACUUM (������� ��).
- pytest tests/test_integration_pipeline.py -q � �������������� smoke-���� runner'� � mock feed.
- python - <<'PY' ... (��. reports/09_research_gate.md) � ������ research pipeline (run_backtests > select_champions).

