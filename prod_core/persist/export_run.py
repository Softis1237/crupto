from __future__ import annotations

import argparse
import os
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

from prod_core.persist import PersistDAO, ParquetSink


def _write_table(sink: ParquetSink, name: str, rows: Iterable[Mapping[str, object]], out_dir: Path) -> None:
    data = list(rows)
    sink.write(name, data)
    if data:
        frame = pd.DataFrame(data)
        frame.to_csv(out_dir / f"{name}.csv", index=False)


def export_run(db_path: str, out_dir: Path, log_path: str | None = None, run_id: str | None = None) -> None:
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"SQLite база не найдена: {db_file}")

    dao = PersistDAO(db_file, run_id=run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    sink = ParquetSink(out_dir)

    resolved_run_id = dao.run_id
    orders = dao.fetch_orders(run_id=resolved_run_id)
    trades = dao.fetch_trades(run_id=resolved_run_id)
    positions = dao.fetch_positions(run_id=resolved_run_id)
    equity_history = dao.fetch_equity_history(run_id=resolved_run_id)
    latency_rows = dao.fetch_latency(run_id=resolved_run_id)

    _write_table(sink, "orders", orders, out_dir)
    _write_table(sink, "trades", trades, out_dir)
    _write_table(sink, "positions", positions, out_dir)
    _write_table(sink, "equity", equity_history, out_dir)
    _write_table(sink, "latency", latency_rows, out_dir)

    summary_lines = ["# Paper Run Summary", ""]
    summary_lines.append(f"* Run ID: {resolved_run_id or 'unknown'}")
    summary_lines.append(f"* Orders: {len(orders)} | Trades: {len(trades)}")

    if equity_history:
        latest = equity_history[0]
        summary_lines.append(f"* Equity (USD): {latest['equity_usd']:.2f} | PnL R cum: {latest['pnl_r_cum']:.2f} | Max DD R: {latest['max_dd_r']:.2f}")
        summary_lines.append(f"* Exposure gross %: {latest['exposure_gross']:.2f} | Exposure net %: {latest['exposure_net']:.2f}")
    summary_lines.append(f"* Open positions: {len(positions)}")
    if log_path:
        summary_lines.append(f"* Log file: {Path(log_path).name}")

    if latency_rows:
        buckets: dict[str, list[float]] = defaultdict(list)
        for row in latency_rows:
            buckets[str(row['stage'])].append(float(row['ms']))
        summary_lines.append("* Latency p95 (ms) by stage:")
        for stage, values in buckets.items():
            values.sort()
            idx = max(int(len(values) * 0.95) - 1, 0)
            summary_lines.append(f"  * {stage}: {values[idx]:.2f}")

    summary_path = out_dir / "summary.md"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    if log_path:
        log_src = Path(log_path)
        if log_src.exists():
            try:
                contents = log_src.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                contents = log_src.read_text(encoding="cp1251", errors="replace")
            (out_dir / log_src.name).write_text(contents, encoding="utf-8")

def main() -> None:
    parser = argparse.ArgumentParser(description="Экспорт результатов paper-прогона")
    parser.add_argument("--db", default="storage/crupto.db", help="Путь к SQLite базе")
    parser.add_argument("--out", required=True, help="Каталог для отчёта")
    parser.add_argument("--log", help="Путь к log-файлу запуска")
    parser.add_argument("--run", help="Идентификатор запуска (по умолчанию из RUN_ID)")
    args = parser.parse_args()
    run_id = args.run or os.getenv("RUN_ID")
    export_run(db_path=args.db, out_dir=Path(args.out), log_path=args.log, run_id=run_id)


if __name__ == "__main__":
    main()
