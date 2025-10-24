from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research_lab.backtests.vectorbt_runner import (
    BacktestResult,
    CandidateConfig,
    load_candidates,
    run_backtests,
    save_results,
)


def _build_sample_csv(path: Path) -> None:
    index = pd.date_range("2024-01-01", periods=180, freq="5min", tz="UTC")
    base = np.linspace(100, 101, len(index))
    close = base.copy()
    close[-10:] -= 1.5  # создаём отклонение для mean-reversion
    high = np.maximum(base + 0.2, close)
    low = np.minimum(base - 0.2, close)
    frame = pd.DataFrame(
        {
            "timestamp": (index.view("int64") // 1_000_000).astype(np.int64),
            "open": base,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(len(index), 10.0),
        }
    )
    frame.to_csv(path, index=False)


def test_load_candidates_parses_symbol_and_timeframe(tmp_path: Path) -> None:
    config_path = tmp_path / "candidates.json"
    config_path.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "strategy": "range_reversion_5m",
                        "candidate_id": "cand-rr",
                        "symbol": "BTC/USDT:USDT",
                        "timeframe": "5m",
                        "deviation_threshold": 0.001,
                        "ema_gap_threshold": 0.02,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    candidates = load_candidates(config_path)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.symbol == "BTC/USDT:USDT"
    assert candidate.timeframe == "5m"
    assert candidate.params["deviation_threshold"] == 0.001


def test_run_backtests_on_csv_dataset(tmp_path: Path) -> None:
    csv_path = tmp_path / "BTC_USDT_USDT_5m.csv"
    _build_sample_csv(csv_path)

    config_path = tmp_path / "candidates.json"
    config_path.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "strategy": "range_reversion_5m",
                        "candidate_id": "cand-rr",
                        "symbol": "BTC/USDT:USDT",
                        "timeframe": "5m",
                        "deviation_threshold": 0.0005,
                        "ema_gap_threshold": 0.05,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    results = run_backtests(
        config_path,
        start="2024-01-01",
        end="2024-01-02",
        csv_root=tmp_path,
        split_ratio=0.6,
    )

    assert len(results) == 1
    result = results[0]
    assert isinstance(result, BacktestResult)
    assert result.candidate_id == "cand-rr"
    assert result.trades >= 1

    out_csv = tmp_path / "results.csv"
    save_results(results, out_csv)
    saved = pd.read_csv(out_csv)
    assert {"candidate_id", "pf_is", "pf_oos", "max_dd", "corr", "trades"} <= set(saved.columns)
