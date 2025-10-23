#!/usr/bin/env bash
set -euo pipefail

RUN_ID=$(date +%Y%m%d_%H%M)
export RUN_ID
OUT_DIR="reports/run_${RUN_ID}"
LOG_DIR="logs"
DB_PATH=${PERSIST_DB_PATH:-storage/crupto.db}

mkdir -p "$OUT_DIR" "$LOG_DIR"
LOG_FILE="${LOG_DIR}/paper24_${RUN_ID}.log"

echo "[crupto] starting 24-hour paper run (output: $OUT_DIR)"

TIMEOUT_CMD="timeout"
if command -v timeout >/dev/null 2>&1; then
  if timeout --help 2>&1 | grep -q -- '--foreground'; then
    TIMEOUT_CMD="timeout --foreground"
  fi
else
  echo "warning: timeout command not found, running without automatic stop" >&2
  TIMEOUT_CMD=""
fi

if [ -n "$TIMEOUT_CMD" ]; then
  { $TIMEOUT_CMD 86400 python -m prod_core.runner --max-seconds 86400 "$@"; } | tee "$LOG_FILE"
  RUN_STATUS=${PIPESTATUS[0]}
else
  python -m prod_core.runner --max-seconds 86400 "$@" | tee "$LOG_FILE"
  RUN_STATUS=${PIPESTATUS[0]}
fi

python -m prod_core.persist.export_run --db "$DB_PATH" --out "$OUT_DIR" --log "$LOG_FILE" --run "$RUN_ID"

echo "[crupto] 24-hour run finished with status $RUN_STATUS"
exit $RUN_STATUS
