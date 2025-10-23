# -*- coding: utf-8 -*-
from pathlib import Path

path = Path("prod_core/persist/export_run.py")
text = path.read_text(encoding="utf-8")
old = "    summary_lines = [\"# Paper Run Summary\", \"\"]\n    summary_lines.append(f\"* Orders: {len(orders)} | Trades: {len(trades)}\")\n\n"
new = "    summary_lines = [\"# Paper Run Summary\", \"\"]\n    summary_lines.append(f\"* Run ID: {resolved_run_id or 'unknown'}\")\n    summary_lines.append(f\"* Orders: {len(orders)} | Trades: {len(trades)}\")\n\n"
if old not in text:
    raise SystemExit("summary block not found")
path.write_text(text.replace(old, new), encoding="utf-8")
