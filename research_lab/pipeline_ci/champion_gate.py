"""Champion/challenger gate helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


@dataclass(slots=True)
class ChampionCriteria:
    min_pf: float = 1.3
    max_dd: float = 1.3
    min_trades: int = 200


@dataclass(slots=True)
class CandidateResult:
    candidate_id: str
    metrics: Dict[str, float]


def passes_gate(metrics: Dict[str, float], criteria: ChampionCriteria | None = None) -> bool:
    criteria = criteria or ChampionCriteria()
    pf = float(metrics.get("pf", 0.0))
    max_dd = float(metrics.get("max_dd", 0.0))
    trades = int(metrics.get("trades", 0))
    return pf >= criteria.min_pf and max_dd <= criteria.max_dd and trades >= criteria.min_trades


def split_candidates(
    results: Iterable[CandidateResult], criteria: ChampionCriteria | None = None
) -> Tuple[List[CandidateResult], List[CandidateResult]]:
    accepted: List[CandidateResult] = []
    rejected: List[CandidateResult] = []
    crit = criteria or ChampionCriteria()
    for result in results:
        (accepted if passes_gate(result.metrics, crit) else rejected).append(result)
    return accepted, rejected


__all__ = ["ChampionCriteria", "CandidateResult", "passes_gate", "split_candidates"]
