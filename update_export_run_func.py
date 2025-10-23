# -*- coding: utf-8 -*-
from pathlib import Path

path = Path("prod_core/persist/export_run.py")
text = path.read_text(encoding="utf-8")
old = "def export_run(db_path: str, out_dir: Path, log_path: str | None = None) -> None:\n    db_file = Path(db_path)\n    if not db_file.exists():\n        raise FileNotFoundError(f\"SQLite ���� �� �������: {db_file}\")\n\n    dao = PersistDAO(db_file)\n    out_dir.mkdir(parents=True, exist_ok=True)\n    sink = ParquetSink(out_dir)\n\n    orders = dao.fetch_orders()\n    trades = dao.fetch_trades()\n    positions = dao.fetch_positions()\n    equity_history = dao.fetch_equity_history()\n    latency_rows = dao.fetch_latency()\n\n"
new = "def export_run(db_path: str, out_dir: Path, log_path: str | None = None, run_id: str | None = None) -> None:\n    db_file = Path(db_path)\n    if not db_file.exists():\n        raise FileNotFoundError(f\"SQLite ���� �� �������: {db_file}\")\n\n    dao = PersistDAO(db_file, run_id=run_id)\n    out_dir.mkdir(parents=True, exist_ok=True)\n    sink = ParquetSink(out_dir)\n\n    resolved_run_id = dao.run_id\n    orders = dao.fetch_orders(run_id=resolved_run_id)\n    trades = dao.fetch_trades(run_id=resolved_run_id)\n    positions = dao.fetch_positions(run_id=resolved_run_id)\n    equity_history = dao.fetch_equity_history(run_id=resolved_run_id)\n    latency_rows = dao.fetch_latency(run_id=resolved_run_id)\n\n"
if old not in text:
    raise SystemExit("export_run signature not found")
path.write_text(text.replace(old, new), encoding="utf-8")
