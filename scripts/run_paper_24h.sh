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

cleanup_old_runs() {
  if ! compgen -G "reports/run_*" >/dev/null; then
    return
  fi
  mapfile -t RUN_DIRS < <(ls -1dt reports/run_* 2>/dev/null)
  if [ "${#RUN_DIRS[@]}" -le 2 ]; then
    return
  fi
  for OLD_DIR in "${RUN_DIRS[@]:2}"; do
    echo "[crupto] removing stale run directory: ${OLD_DIR}"
    rm -rf "${OLD_DIR}"
  done
}

TIMEOUT_CMD="timeout"
if command -v timeout >/dev/null 2>&1; then
  if timeout --help 2>&1 | grep -q -- '--foreground'; then
    TIMEOUT_CMD="timeout --foreground"
  fi
else
  echo "warning: timeout command not found, running without automatic stop" >&2
  TIMEOUT_CMD=""
fi

MAX_RESTARTS=${MAX_RESTARTS:-5}
RESTART_DELAY_SEC=${RESTART_DELAY_SEC:-30}
attempt=1
RUN_STATUS=1

while true; do
  echo "[crupto] runner attempt ${attempt} (max ${MAX_RESTARTS})"
  if [ -n "$TIMEOUT_CMD" ]; then
    { $TIMEOUT_CMD 86400 python -m prod_core.runner --max-seconds 86400 "$@"; } | tee "$LOG_FILE"
    RUN_STATUS=${PIPESTATUS[0]}
  else
    python -m prod_core.runner --max-seconds 86400 "$@" | tee "$LOG_FILE"
    RUN_STATUS=${PIPESTATUS[0]}
  fi

  if [ "$RUN_STATUS" -eq 0 ] || [ "$RUN_STATUS" -eq 124 ]; then
    echo "[crupto] runner completed with status ${RUN_STATUS}"
    break
  fi

  if [ "$attempt" -ge "$MAX_RESTARTS" ]; then
    echo "[crupto] runner failed with status ${RUN_STATUS}, reached max restarts (${MAX_RESTARTS})."
    break
  fi

  echo "[crupto] runner crashed with status ${RUN_STATUS}, restarting in ${RESTART_DELAY_SEC}s..."
  sleep "$RESTART_DELAY_SEC"
  attempt=$((attempt + 1))
done

python -m prod_core.persist.export_run --db "$DB_PATH" --out "$OUT_DIR" --log "$LOG_FILE" --run "$RUN_ID"
cleanup_old_runs

echo "[crupto] 24-hour run finished with status $RUN_STATUS"
exit $RUN_STATUS
