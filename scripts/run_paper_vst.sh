#!/usr/bin/env bash
set -euo pipefail

MAX_SECONDS="${MAX_SECONDS:-28800}" # 8 hours by default
RUN_ID="${RUN_ID:-vst_$(date +%Y%m%d_%H%M%S)}"
REPORT_DIR="reports/run_${RUN_ID}"
LOG_FILE="${REPORT_DIR}/paper_vst.log"
SUMMARY_FILE="${REPORT_DIR}/virtual_summary.md"
DB_PATH="${PERSIST_DB_PATH:-storage/crupto.db}"

mkdir -p "${REPORT_DIR}"

export MODE=paper
export USE_VIRTUAL_TRADING=true
export RUN_ID="${RUN_ID}"
export VIRTUAL_ASSET="${VIRTUAL_ASSET:-VST}"
export VIRTUAL_EQUITY="${VIRTUAL_EQUITY:-10000}"

echo "[run_paper_vst] Starting paper loop for run ${RUN_ID} (max ${MAX_SECONDS}s)"
python -m prod_core.runner --max-seconds "${MAX_SECONDS}" "$@" | tee "${LOG_FILE}"

if [[ -f "reports/telemetry_events.csv" ]]; then
  cp "reports/telemetry_events.csv" "${REPORT_DIR}/telemetry_events.csv"
fi

python - <<'PY' "${DB_PATH}" "${RUN_ID}" "${SUMMARY_FILE}"
import json
import os
import sys
from pathlib import Path

from prod_core.persist import PersistDAO

db_path = Path(sys.argv[1])
run_id = sys.argv[2]
summary_file = Path(sys.argv[3])

dao = PersistDAO(db_path.as_posix(), run_id=run_id)
orders = dao.fetch_orders(run_id=run_id)
trades = dao.fetch_trades(run_id=run_id)
equity = dao.fetch_equity_last(run_id=run_id)
virtual_asset = os.getenv("VIRTUAL_ASSET", "VST")

summary_lines = [
    f"# Virtual paper report — {run_id}",
    "",
    f"- Virtual asset: `{virtual_asset}`",
    f"- Orders recorded: {len(orders)}",
    f"- Trades recorded: {len(trades)}",
    f"- Cumulative PnL (risk units): {equity['pnl_r_cum'] if equity else 0.0}",
    f"- Max drawdown (risk units): {equity['max_dd_r'] if equity else 0.0}",
    "",
    "## Trades",
]

for trade in trades:
    meta = trade.get("meta") or {}
    summary_lines.append(
        f"- {trade['ts']}: {trade['symbol']} {trade['side']} qty={trade['qty']} "
        f"price={trade['price']} pnl_r={trade['pnl_r']} meta={json.dumps(meta, ensure_ascii=False)}"
    )

summary_file.write_text("\n".join(summary_lines), encoding="utf-8")
PY

echo "[run_paper_vst] Report saved to ${SUMMARY_FILE}"
