from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple, Type

import pandas as pd

from prod_core.strategies import (
    Breakout4HStrategy,
    FundingReversionStrategy,
    RangeReversion5MStrategy,
    VolatilityExpansion15MStrategy,
)
from prod_core.strategies.breakout_4h import BreakoutConfig
from prod_core.strategies.base import TradingStrategy
from prod_core.strategies.funding_rev import FundingReversionConfig
from prod_core.strategies.range_rev_5m import RangeReversionConfig
from prod_core.strategies.vol_exp_15m import VolatilityExpansionConfig

STRATEGY_REGISTRY: Dict[str, Tuple[Type[TradingStrategy], Type]] = {
    "breakout_4h": (Breakout4HStrategy, BreakoutConfig),
    "range_reversion_5m": (RangeReversion5MStrategy, RangeReversionConfig),
    "volatility_expansion_15m": (VolatilityExpansion15MStrategy, VolatilityExpansionConfig),
    "funding_reversion": (FundingReversionStrategy, FundingReversionConfig),
}


@dataclass(slots=True)
class CandidateConfig:
    """Description of a strategy candidate for evaluation."""

    strategy: str
    candidate_id: str
    params: Dict[str, float]


@dataclass(slots=True)
class BacktestResult:
    """Backtest outcome for a candidate."""

    candidate_id: str
    strategy: str
    pf: float
    max_dd: float
    trades: int


def _row_to_candidate(row: Dict[str, object]) -> CandidateConfig:
    strategy = str(row.get("strategy", ""))
    if strategy not in STRATEGY_REGISTRY:
        raise ValueError(f"Unsupported strategy '{strategy}' in candidate file")
    candidate_id = str(row.get("id", row.get("name", f"candidate_{strategy}")))
    params = {k: float(v) for k, v in row.items() if k not in {"strategy", "id", "name"}}
    return CandidateConfig(strategy=strategy, candidate_id=candidate_id, params=params)


def load_candidates(path: Path) -> List[CandidateConfig]:
    """Load candidate configurations from CSV or JSON."""

    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("candidates", [])
        if not isinstance(data, list):
            raise ValueError("JSON candidates file must contain a list")
        return [_row_to_candidate(entry) for entry in data]

    frame = pd.read_csv(path)
    rows = frame.to_dict(orient="records")
    return [_row_to_candidate(row) for row in rows]


def run_batch(configs: Iterable[CandidateConfig]) -> List[BacktestResult]:
    """Run a deterministic placeholder backtest for each candidate."""

    results: List[BacktestResult] = []
    for cfg in configs:
        params_sum = sum(cfg.params.values()) if cfg.params else 0.0
        pf = 1.0 + 0.1 * ((params_sum or 1.0) % 5)
        max_dd = 0.8 + 0.05 * ((len(cfg.params) % 4) + 1)
        trades = 80 + int(abs(params_sum)) % 120
        results.append(
            BacktestResult(
                candidate_id=cfg.candidate_id,
                strategy=cfg.strategy,
                pf=float(f"{pf:.3f}"),
                max_dd=float(f"{max_dd:.3f}"),
                trades=trades,
            )
        )
    return results


def save_results(results: Sequence[BacktestResult], path: Path) -> None:
    """Persist backtest results to CSV."""

    records = [
        {
            "candidate_id": r.candidate_id,
            "strategy": r.strategy,
            "pf": r.pf,
            "max_dd": r.max_dd,
            "trades": r.trades,
        }
        for r in results
    ]
    frame = pd.DataFrame(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def build_strategy(candidate: CandidateConfig) -> TradingStrategy:
    """Instantiate a TradingStrategy from candidate definition."""

    if candidate.strategy not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy type '{candidate.strategy}'")
    strategy_cls, config_cls = STRATEGY_REGISTRY[candidate.strategy]
    config = config_cls(**candidate.params) if candidate.params else None
    strategy = strategy_cls(config=config) if config is not None else strategy_cls()
    setattr(strategy, "shadow_id", candidate.candidate_id)
    return strategy


def load_shadow_strategies(path: Path) -> List[TradingStrategy]:
    """Load TradingStrategy instances for shadow execution."""

    return [build_strategy(candidate) for candidate in load_candidates(path)]


def run_backtests(
    config_path: Path | str,
    *,
    start: str | None = None,
    end: str | None = None,
    save_csv: Path | None = None,
    save_json: Path | None = None,
) -> List[BacktestResult]:
    """Запускает бэктесты для списка кандидатов (заглушка для vectorbt)."""

    path = Path(config_path)
    candidates = load_candidates(path)
    # TODO: заменить run_batch на реальный vectorbt workflow (price loader + custom strategy).
    results = run_batch(candidates)

    if save_csv:
        save_results(results, Path(save_csv))
    if save_json:
        records = [
            {
                "candidate_id": r.candidate_id,
                "strategy": r.strategy,
                "pf": r.pf,
                "max_dd": r.max_dd,
                "trades": r.trades,
                "start": start,
                "end": end,
            }
            for r in results
        ]
        Path(save_json).parent.mkdir(parents=True, exist_ok=True)
        Path(save_json).write_text(json.dumps({"results": records}, indent=2), encoding="utf-8")
    return results


__all__ = [
    "CandidateConfig",
    "BacktestResult",
    "load_candidates",
    "run_batch",
    "save_results",
    "build_strategy",
    "load_shadow_strategies",
    "run_backtests",
]
