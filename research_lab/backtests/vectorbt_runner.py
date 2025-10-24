from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple, Type, Union, get_args, get_origin

import numpy as np
import pandas as pd
import vectorbt as vbt

from prod_core.data.features import FeatureEngineer
from prod_core.strategies import (
    Breakout4HStrategy,
    FundingReversionStrategy,
    RangeReversion5MStrategy,
    VolatilityExpansion15MStrategy,
)
from prod_core.strategies.base import TradingStrategy
from prod_core.strategies.breakout_4h import BreakoutConfig
from prod_core.strategies.funding_rev import FundingReversionConfig
from prod_core.strategies.range_rev_5m import RangeReversionConfig
from prod_core.strategies.vol_exp_15m import VolatilityExpansionConfig

try:
    import ccxt  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - ccxt необязателен при использовании локальных CSV
    ccxt = None


STRATEGY_REGISTRY: Dict[str, Tuple[Type[TradingStrategy], Type]] = {
    "breakout_4h": (Breakout4HStrategy, BreakoutConfig),
    "range_reversion_5m": (RangeReversion5MStrategy, RangeReversionConfig),
    "volatility_expansion_15m": (VolatilityExpansion15MStrategy, VolatilityExpansionConfig),
    "funding_reversion": (FundingReversionStrategy, FundingReversionConfig),
}


@dataclass(slots=True)
class CandidateConfig:
    """Настройка кандидата, пригодная для shadow-режима и research-пайплайна."""

    strategy: str
    candidate_id: str
    params: Dict[str, float]
    symbol: str | None = None
    timeframe: str | None = None
    source: str | None = None
    csv_path: str | None = None


@dataclass(slots=True)
class BacktestResult:
    """Метрики бэктеста кандидата."""

    candidate_id: str
    strategy: str
    pf_is: float
    pf_oos: float
    max_dd: float
    corr: float
    trades: int


def _row_to_candidate(row: Dict[str, object]) -> CandidateConfig:
    strategy = str(row.get("strategy", "")).strip()
    if strategy not in STRATEGY_REGISTRY:
        raise ValueError(f"Unsupported strategy '{strategy}' in candidate file")
    candidate_id = str(row.get("candidate_id") or row.get("id") or row.get("name") or "candidate")
    params = {
        k: float(v)
        for k, v in row.items()
        if k not in {"strategy", "candidate_id", "id", "name", "symbol", "timeframe", "source", "csv_path"}
        and v is not None
    }
    symbol = row.get("symbol")
    timeframe = row.get("timeframe")
    source = row.get("source")
    csv_path = row.get("csv_path")
    return CandidateConfig(
        strategy=strategy,
        candidate_id=candidate_id,
        params=params,
        symbol=str(symbol).strip() if symbol else None,
        timeframe=str(timeframe).strip() if timeframe else None,
        source=str(source).strip() if source else None,
        csv_path=str(csv_path).strip() if csv_path else None,
    )


def load_candidates(path: Path) -> List[CandidateConfig]:
    """Загружает описание кандидатов из CSV или JSON."""

    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("candidates") or data.get("results") or []
        if not isinstance(data, list):
            raise ValueError("JSON candidates file must contain a list")
        return [_row_to_candidate(entry) for entry in data]

    frame = pd.read_csv(path)
    rows = frame.to_dict(orient="records")
    return [_row_to_candidate(row) for row in rows]


def timeframe_to_milliseconds(timeframe: str) -> int:
    unit = timeframe[-1].lower()
    value = int(timeframe[:-1])
    mapping = {
        "m": 60_000,
        "h": 3_600_000,
        "d": 86_400_000,
    }
    if unit not in mapping:
        raise ValueError(f"Unsupported timeframe '{timeframe}'")
    return value * mapping[unit]


def _normalize_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result = result.sort_index()
    result = result[~result.index.duplicated(keep="last")]
    return result


def _load_from_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    if "timestamp" not in frame.columns:
        raise ValueError(f"CSV {path} must contain 'timestamp' column in milliseconds or ISO8601 format.")
    ts = frame["timestamp"]
    if np.issubdtype(ts.dtype, np.number):
        index = pd.to_datetime(ts, unit="ms", utc=True)
    else:
        index = pd.to_datetime(ts, utc=True)
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"CSV {path} missing columns: {', '.join(sorted(missing))}")
    data = frame[list(required | {"funding_rate"})] if "funding_rate" in frame.columns else frame[list(required)]
    data.index = index
    data = data.astype(float)
    return _normalize_dataframe(data)


def _fetch_ccxt(
    exchange_id: str,
    symbol: str,
    timeframe: str,
    start: pd.Timestamp | None,
    end: pd.Timestamp | None,
) -> pd.DataFrame:
    if ccxt is None:
        raise RuntimeError("ccxt is not installed; provide CSV data via --csv-root или csv_path.")
    client = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    since_ms = int(start.timestamp() * 1000) if start else None
    end_ms = int(end.timestamp() * 1000) if end else None
    step = timeframe_to_milliseconds(timeframe)
    all_rows: list[list[float]] = []
    limit = 1000
    while True:
        batch = client.fetch_ohlcv(symbol, timeframe=timeframe, since=since_ms, limit=limit)
        if not batch:
            break
        all_rows.extend(batch)
        last_ts = batch[-1][0]
        if end_ms and last_ts >= end_ms:
            break
        if since_ms is not None and last_ts <= since_ms:
            break
        since_ms = (last_ts or 0) + step
        if end_ms and since_ms >= end_ms:
            break
        if len(batch) < limit:
            break
    if not all_rows:
        raise RuntimeError(f"ccxt returned no data for {symbol} {timeframe}")
    frame = pd.DataFrame(
        all_rows,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    frame.set_index("timestamp", inplace=True)
    if end:
        frame = frame.loc[:end]
    if start:
        frame = frame.loc[start:]
    return _normalize_dataframe(frame.astype(float))


def _resolve_type(annotation: Type) -> Type:
    origin = get_origin(annotation)
    if origin is None:
        return annotation
    if origin is Union:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]  # noqa: E721
        return args[0] if args else annotation
    return annotation


def _coerce_param(value: float, target_type: Type) -> float | int | float:
    target = _resolve_type(target_type)
    if target in (int, "int"):
        return int(value)
    if target in (float, "float"):
        return float(value)
    return value


def build_strategy(candidate: CandidateConfig) -> TradingStrategy:
    """Инстанцирует TradingStrategy из описания кандидата."""

    if candidate.strategy not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy type '{candidate.strategy}'")
    strategy_cls, config_cls = STRATEGY_REGISTRY[candidate.strategy]
    config: TradingStrategy | None
    if candidate.params:
        config_kwargs: Dict[str, float | int | float] = {}
        for field in fields(config_cls):
            if field.name not in candidate.params:
                continue
            value = candidate.params[field.name]
            if value is None:
                continue
            config_kwargs[field.name] = _coerce_param(value, field.type)
        config = config_cls(**config_kwargs) if config_kwargs else config_cls()
    else:
        config = config_cls()
    strategy = strategy_cls(config=config) if config is not None else strategy_cls()
    setattr(strategy, "shadow_id", candidate.candidate_id)
    return strategy


def load_shadow_strategies(path: Path) -> List[TradingStrategy]:
    """Список стратегий для shadow-режима."""

    return [build_strategy(candidate) for candidate in load_candidates(path)]


def _profit_factor(pnl: pd.Series) -> float:
    gains = pnl[pnl > 0].sum()
    losses = pnl[pnl < 0].sum()
    if losses >= 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / abs(losses))


def _compute_max_drawdown(value: pd.Series) -> float:
    if value.empty:
        return 0.0
    peak = value.cummax()
    drawdown = (value - peak) / peak
    return float(abs(drawdown.min()))


def _sanitize_symbol(symbol: str) -> str:
    return symbol.replace("/", "_").replace(":", "_").replace("-", "_")


def _generate_signals(
    strategy: TradingStrategy,
    candles: pd.DataFrame,
    features: pd.DataFrame,
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    index = features.index
    candles = candles.loc[index]
    long_entries = pd.Series(False, index=index)
    long_exits = pd.Series(False, index=index)
    short_entries = pd.Series(False, index=index)
    short_exits = pd.Series(False, index=index)

    position: str | None = None
    entry_idx = -1
    min_hold = max(1, strategy.min_hold_bars)

    for idx, ts in enumerate(index):
        slice_candles = candles.iloc[: idx + 1]
        slice_features = features.iloc[: idx + 1]
        if len(slice_candles) < 2 or slice_features.empty:
            continue
        signals = strategy._generate(slice_candles, slice_features)

        if position is None:
            chosen = None
            for signal in signals:
                if signal.side == "long":
                    chosen = "long"
                    break
                if signal.side == "short":
                    chosen = "short"
                    break
            if chosen == "long":
                long_entries.iloc[idx] = True
                position = "long"
                entry_idx = idx
            elif chosen == "short":
                short_entries.iloc[idx] = True
                position = "short"
                entry_idx = idx
            continue

        hold_elapsed = idx - entry_idx
        if hold_elapsed < min_hold:
            continue

        if position == "long":
            long_exits.iloc[idx] = True
        else:
            short_exits.iloc[idx] = True
        position = None
        entry_idx = -1

    if position == "long":
        long_exits.iloc[-1] = True
    elif position == "short":
        short_exits.iloc[-1] = True

    return long_entries, long_exits, short_entries, short_exits


def _run_candidate_backtest(
    candidate: CandidateConfig,
    candles: pd.DataFrame,
    split_ratio: float,
) -> BacktestResult:
    strategy = build_strategy(candidate)
    engineer = FeatureEngineer()
    features = engineer.build(candles)
    if features.empty:
        return BacktestResult(candidate.candidate_id, candidate.strategy, 0.0, 0.0, 0.0, 0.0, 0)

    candles = candles.loc[features.index]
    long_entries, long_exits, short_entries, short_exits = _generate_signals(strategy, candles, features)

    if long_entries.sum() == 0 and short_entries.sum() == 0:
        return BacktestResult(candidate.candidate_id, candidate.strategy, 0.0, 0.0, 0.0, 0.0, 0)

    close = candles["close"]
    portfolio = vbt.Portfolio.from_signals(
        close,
        entries=long_entries,
        exits=long_exits,
        short_entries=short_entries,
        short_exits=short_exits,
        freq=strategy.timeframe,
    )
    trades_records = portfolio.trades.records
    trades = int(portfolio.trades.count())

    if trades == 0:
        return BacktestResult(candidate.candidate_id, candidate.strategy, 0.0, 0.0, 0.0, 0.0, 0)

    pnl = trades_records["pnl"]
    split_idx = max(1, min(len(close) - 1, int(len(close) * split_ratio)))
    pf_is = _profit_factor(pnl[trades_records["exit_idx"] < split_idx])
    pf_oos = _profit_factor(pnl[trades_records["exit_idx"] >= split_idx])

    equity = portfolio.value()
    max_dd = _compute_max_drawdown(equity)

    returns = portfolio.returns().dropna()
    base_returns = close.pct_change().reindex(returns.index).fillna(0.0)
    corr = float(returns.corr(base_returns)) if len(returns) > 1 else 0.0
    if np.isnan(corr):
        corr = 0.0

    return BacktestResult(candidate.candidate_id, candidate.strategy, pf_is, pf_oos, max_dd, corr, trades)


def run_backtests(
    config_path: Path | str,
    *,
    start: str | None = None,
    end: str | None = None,
    save_csv: Path | None = None,
    save_json: Path | None = None,
    exchange: str = "binanceusdm",
    csv_root: Path | None = None,
    split_ratio: float = 0.7,
) -> List[BacktestResult]:
    """Запускает backtests для списка кандидатов с использованием vectorbt."""

    candidates = load_candidates(Path(config_path))
    start_ts = pd.Timestamp(start, tz="UTC") if start else None
    end_ts = pd.Timestamp(end, tz="UTC") if end else None
    price_cache: Dict[Tuple[str, str], pd.DataFrame] = {}
    results: List[BacktestResult] = []

    for candidate in candidates:
        if not candidate.symbol or not candidate.timeframe:
            raise ValueError(f"Candidate {candidate.candidate_id} must define 'symbol' and 'timeframe' for backtests.")
        key = (candidate.symbol, candidate.timeframe)
        if key not in price_cache:
            data_frame: pd.DataFrame
            if candidate.csv_path:
                data_frame = _load_from_csv(Path(candidate.csv_path))
            elif csv_root:
                csv_guess = csv_root / f"{_sanitize_symbol(candidate.symbol)}_{candidate.timeframe}.csv"
                if csv_guess.exists():
                    data_frame = _load_from_csv(csv_guess)
                else:
                    data_frame = _fetch_ccxt(exchange, candidate.symbol, candidate.timeframe, start_ts, end_ts)
            else:
                data_frame = _fetch_ccxt(exchange, candidate.symbol, candidate.timeframe, start_ts, end_ts)
            price_cache[key] = data_frame
        candles = price_cache[key]
        window = candles.copy()
        if start_ts:
            window = window.loc[start_ts:]
        if end_ts:
            window = window.loc[:end_ts]
        if window.empty:
            results.append(BacktestResult(candidate.candidate_id, candidate.strategy, 0.0, 0.0, 0.0, 0.0, 0))
            continue
        results.append(_run_candidate_backtest(candidate, window, split_ratio))

    if save_csv:
        save_results(results, save_csv)
    if save_json:
        records = [
            {
                "candidate_id": r.candidate_id,
                "strategy": r.strategy,
                "pf_is": r.pf_is,
                "pf_oos": r.pf_oos,
                "max_dd": r.max_dd,
                "corr": r.corr,
                "trades": r.trades,
                "start": start,
                "end": end,
            }
            for r in results
        ]
        save_json.parent.mkdir(parents=True, exist_ok=True)
        save_json.write_text(json.dumps({"results": records}, indent=2), encoding="utf-8")
    return results


def save_results(results: Sequence[BacktestResult], path: Path) -> None:
    """Сохраняет метрики кандидатов в CSV."""

    records = [
        {
            "candidate_id": r.candidate_id,
            "strategy": r.strategy,
            "pf_is": r.pf_is,
            "pf_oos": r.pf_oos,
            "max_dd": r.max_dd,
            "corr": r.corr,
            "trades": r.trades,
        }
        for r in results
    ]
    frame = pd.DataFrame(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="vectorbt backtest runner for crupto candidates.")
    parser.add_argument("--config", required=True, help="путь к JSON/CSV со списком кандидатов")
    parser.add_argument("--start", help="начало периода (например, 2024-01-01)")
    parser.add_argument("--end", help="окончание периода (например, 2024-04-01)")
    parser.add_argument("--exchange", default="binanceusdm", help="биржа ccxt для загрузки данных (по умолчанию binanceusdm)")
    parser.add_argument("--csv-root", help="каталог с CSV-файлами вида SYMBOL_TIMEFRAME.csv")
    parser.add_argument("--split-ratio", type=float, default=0.7, help="доля данных для in-sample (0..1)")
    parser.add_argument("--save-csv", help="куда сохранить результаты в CSV")
    parser.add_argument("--save-json", help="куда сохранить результаты в JSON")
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    csv_root = Path(args.csv_root) if args.csv_root else None
    save_csv = Path(args.save_csv) if args.save_csv else None
    save_json = Path(args.save_json) if args.save_json else None

    run_backtests(
        args.config,
        start=args.start,
        end=args.end,
        save_csv=save_csv,
        save_json=save_json,
        exchange=args.exchange,
        csv_root=csv_root,
        split_ratio=args.split_ratio,
    )


__all__ = [
    "CandidateConfig",
    "BacktestResult",
    "load_candidates",
    "run_backtests",
    "save_results",
    "build_strategy",
    "load_shadow_strategies",
]


if __name__ == "__main__":
    main()
