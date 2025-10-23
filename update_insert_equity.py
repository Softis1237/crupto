# -*- coding: utf-8 -*-
from pathlib import Path

path = Path("prod_core/persist/dao.py")
lines = path.read_text(encoding="utf-8").splitlines()
for idx, line in enumerate(lines):
    if line.strip().startswith('def insert_equity_snapshot'):
        start = idx
        end = start
        while end < len(lines) and not lines[end].strip().startswith('def insert_latency'):
            end += 1
        lines[start:end] = [
            "    def insert_equity_snapshot(self, payload: EquitySnapshotPayload) -> None:",
            "        \"\"\"������� equity � ��-����.\"\"\"",
            "",
            "        run_id = self._resolve_run_id(payload.run_id)",
            "        with self.transaction() as conn:",
            "            conn.execute(",
            "                \"\"\"",
            "                INSERT OR REPLACE INTO equity_snapshots",
            "                (ts, run_id, equity_usd, pnl_r_cum, max_dd_r, exposure_gross, exposure_net)",
            "                VALUES (?, ?, ?, ?, ?, ?, ?)",
            "                \"\"\"",
            "                (",
            "                    payload.ts,",
            "                    run_id,",
            "                    payload.equity_usd,",
            "                    payload.pnl_r_cum,",
            "                    payload.max_dd_r,",
            "                    payload.exposure_gross,",
            "                    payload.exposure_net,",
            "                ),",
            "            )",
            "",
        ]
        break
else:
    raise SystemExit("insert_equity_snapshot not found")
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
