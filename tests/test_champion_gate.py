from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from research_lab.pipeline_ci.champion_gate import (
    ChampionCriteria,
    CandidateResult,
    load_results,
    passes_gate,
    select_champions,
    split_candidates,
)


def test_passes_gate_with_new_metrics() -> None:
    metrics = {
        "pf_is": 1.5,
        "pf_oos": 1.2,
        "max_dd": 1.0,
        "corr": 0.2,
        "trades": 250,
    }
    assert passes_gate(metrics, ChampionCriteria())


def test_split_and_select(tmp_path: Path) -> None:
    data = [
        {"candidate_id": "cand-ok", "pf_is": 1.4, "pf_oos": 1.2, "max_dd": 1.1, "corr": 0.3, "trades": 220},
        {"candidate_id": "cand-bad", "pf_is": 1.0, "pf_oos": 0.9, "max_dd": 1.6, "corr": 0.5, "trades": 120},
    ]
    csv_path = tmp_path / "results.csv"
    pd.DataFrame(data).to_csv(csv_path, index=False)

    results = load_results(csv_path)
    accepted, rejected = split_candidates(results)
    assert len(accepted) == 1
    assert accepted[0].candidate_id == "cand-ok"
    assert len(rejected) == 1
    assert not passes_gate(rejected[0].metrics)

    json_path = tmp_path / "results.json"
    json_path.write_text(json.dumps({"results": data}), encoding="utf-8")
    champions = select_champions(json_path)
    assert [c.candidate_id for c in champions] == ["cand-ok"]
