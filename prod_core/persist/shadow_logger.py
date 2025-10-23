from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd


@dataclass(slots=True)
class ShadowLogRecord:
    run_id: str
    strategy_id: str
    symbol: str
    timeframe: str
    timestamp: datetime
    side: str
    price: float
    confidence: float
    expected_rr: float
    metadata: Dict[str, Any]


class ShadowLogger:
    """Persist challenger decisions for later analysis."""

    def __init__(self, base_dir: Path, run_id: str) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id

    def _path_for(self, strategy_id: str) -> Path:
        safe = strategy_id.replace('/', '_')
        return self.base_dir / f"{safe}.csv"

    def log(self, record: ShadowLogRecord) -> None:
        path = self._path_for(record.strategy_id)
        file_exists = path.exists()
        with path.open('a', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    'run_id',
                    'strategy_id',
                    'symbol',
                    'timeframe',
                    'timestamp',
                    'side',
                    'price',
                    'confidence',
                    'expected_rr',
                    'metadata',
                ],
            )
            if not file_exists:
                writer.writeheader()
            writer.writerow(
                {
                    'run_id': record.run_id,
                    'strategy_id': record.strategy_id,
                    'symbol': record.symbol,
                    'timeframe': record.timeframe,
                    'timestamp': record.timestamp.isoformat(),
                    'side': record.side,
                    'price': f"{record.price:.6f}",
                    'confidence': f"{record.confidence:.4f}",
                    'expected_rr': f"{record.expected_rr:.6f}",
                    'metadata': json.dumps(record.metadata, ensure_ascii=False),
                }
            )
        try:
            frame = pd.read_csv(path)
            frame.to_parquet(path.with_suffix('.parquet'), index=False)
        except Exception:
            pass
