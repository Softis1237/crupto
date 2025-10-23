"""Champion/challenger gate helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd


@dataclass(slots=True)
class ChampionCriteria:
    """Допуски для перехода кандидата в paper-режим."""

    min_pf_is: float = 1.3
    min_pf_oos: float = 1.1
    max_dd: float = 1.3
    max_corr: float = 0.4
    min_trades: int = 200


@dataclass(slots=True)
class CandidateResult:
    candidate_id: str
    metrics: Dict[str, float]


NUMERIC_ALIASES = {
    "pf": ("pf", "pf_is", "pf_in_sample"),
    "pf_oos": ("pf_oos", "pf_out_sample", "pf_out"),
    "max_dd": ("max_dd", "max_drawdown"),
    "corr": ("corr", "corr_with_portfolio"),
    "trades": ("trades", "n_trades"),
}


def _extract_metric(metrics: Dict[str, float], keys: Tuple[str, ...], default: float = 0.0) -> float:
    for key in keys:
        if key in metrics:
            try:
                return float(metrics[key])
            except (TypeError, ValueError):
                return default
    return default


def passes_gate(metrics: Dict[str, float], criteria: ChampionCriteria | None = None) -> bool:
    crit = criteria or ChampionCriteria()
    pf_is = _extract_metric(metrics, NUMERIC_ALIASES["pf"])
    pf_oos = _extract_metric(metrics, NUMERIC_ALIASES["pf_oos"], default=pf_is)
    max_dd = _extract_metric(metrics, NUMERIC_ALIASES["max_dd"])
    corr = abs(_extract_metric(metrics, NUMERIC_ALIASES["corr"]))
    trades = int(_extract_metric(metrics, NUMERIC_ALIASES["trades"]))
    return (
        pf_is >= crit.min_pf_is
        and pf_oos >= crit.min_pf_oos
        and max_dd <= crit.max_dd
        and corr <= crit.max_corr
        and trades >= crit.min_trades
    )


def split_candidates(
    results: Iterable[CandidateResult], criteria: ChampionCriteria | None = None
) -> Tuple[List[CandidateResult], List[CandidateResult]]:
    accepted: List[CandidateResult] = []
    rejected: List[CandidateResult] = []
    crit = criteria or ChampionCriteria()
    for result in results:
        (accepted if passes_gate(result.metrics, crit) else rejected).append(result)
    return accepted, rejected


def _row_to_candidate(row: Dict[str, object]) -> CandidateResult:
    candidate_id = str(row.get("candidate_id") or row.get("id") or row.get("name") or "candidate")
    metrics: Dict[str, float] = {}
    for key, value in row.items():
        if key in {"candidate_id", "id", "name"}:
            continue
        try:
            metrics[key] = float(value)
        except (TypeError, ValueError):
            continue
    return CandidateResult(candidate_id=candidate_id, metrics=metrics)


def load_results(path: Path | str) -> List[CandidateResult]:
    """Загружает результаты бэктеста из CSV или JSON."""

    location = Path(path)
    if not location.exists():
        raise FileNotFoundError(location)
    if location.suffix.lower() == ".json":
        data = json.loads(location.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("results") or data.get("candidates") or []
        if not isinstance(data, list):
            raise ValueError("JSON файл должен содержать список результатов")
        return [_row_to_candidate(entry) for entry in data]

    frame = pd.read_csv(location)
    return [_row_to_candidate(row) for row in frame.to_dict(orient="records")]


def select_champions(
    path: Path | str,
    *,
    criteria: ChampionCriteria | None = None,
) -> List[CandidateResult]:
    """Возвращает список кандидатов, прошедших champion-gate."""

    results = load_results(path)
    accepted, _ = split_candidates(results, criteria)
    return accepted


__all__ = [
    "ChampionCriteria",
    "CandidateResult",
    "passes_gate",
    "split_candidates",
    "load_results",
    "select_champions",
]
