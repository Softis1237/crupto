#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sqlite3
import time
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

from prod_core.persist import ParquetSink

TABLES = ["orders", "trades", "positions", "equity_snapshots", "latency"]

def _rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, object]]:
    return [dict(row) for row in rows]

def export_run(conn: sqlite3.Connection, run_id: str, out_dir: Path, dry_run: bool = False) -> None:
    run_dir = out_dir / f"run_{run_id.replace('/', '_')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    sink = ParquetSink(run_dir)

    for table in TABLES:
        cursor = conn.execute(f"SELECT * FROM {table} WHERE run_id = ?", (run_id,))
        rows = _rows_to_dicts(cursor.fetchall())
        if dry_run:
            print(f"[dry-run] would export {len(rows)} rows from {table} for run {run_id}")
        else:
            sink.write(table, rows)
            if rows:
                frame = pd.DataFrame(rows)
                frame.to_csv(run_dir / f"{table}.csv", index=False)
            conn.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))

def gather_runs(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT run_id, MAX(ts) as last_ts FROM equity_snapshots WHERE run_id IS NOT NULL GROUP BY run_id"
    ).fetchall()
    result: dict[str, int] = {}
    for row in rows:
        if row["run_id"]:
            result[str(row["run_id"])] = int(row["last_ts"] or 0)
    return result

def vacuum_and_rotate(db_path: Path, out_dir: Path, keep_days: int, keep_runs: int, dry_run: bool = False) -> None:
    conn = sqlite3.connect(db_path.as_posix())
    conn.row_factory = sqlite3.Row
    try:
        run_meta = gather_runs(conn)
        if not run_meta:
            print("Нет run_id для ротации (таблица equity_snapshots пуста).")
            return

        sorted_runs = sorted(run_meta.items(), key=lambda item: item[1], reverse=True)
        now = int(time.time())
        cutoff = now - keep_days * 86400

        keep_set = {run for run, _ in sorted_runs[:keep_runs]}
        for run, last_ts in sorted_runs:
            if last_ts >= cutoff:
                keep_set.add(run)

        to_rotate = [run for run, _ in sorted_runs if run not in keep_set and run != "legacy"]
        if not to_rotate:
            print("Ротация не требуется: все run_id попадают в окно хранения.")
            return

        print(f"Будут перемещены {len(to_rotate)} run_id: {', '.join(to_rotate)}")
        out_dir.mkdir(parents=True, exist_ok=True)

        for run_id in to_rotate:
            export_run(conn, run_id, out_dir, dry_run=dry_run)

        if dry_run:
            print("[dry-run] пропускаем VACUUM и commit")
            return

        conn.execute("VACUUM")
        conn.commit()
        print("Ротация завершена, VACUUM выполнен.")
    finally:
        conn.close()

def main() -> None:
    parser = argparse.ArgumentParser(description="VACUUM и выгрузка старых run_id в Parquet")
    parser.add_argument("--db", default="storage/crupto.db", help="Путь к SQLite базе")
    parser.add_argument("--out", default="reports/archive", help="Каталог для архива (по run_id)")
    parser.add_argument("--keep-days", type=int, default=7, help="Сколько дней истории хранить в SQLite")
    parser.add_argument("--keep-runs", type=int, default=5, help="Сколько последних run_id всегда сохранять")
    parser.add_argument("--dry-run", action="store_true", help="Только показать план без удаления")
    args = parser.parse_args()

    vacuum_and_rotate(
        db_path=Path(args.db),
        out_dir=Path(args.out),
        keep_days=args.keep_days,
        keep_runs=args.keep_runs,
        dry_run=args.dry_run,
    )

if __name__ == "__main__":
    main()
