import asyncio
from typing import Dict, List, Tuple

import pandas as pd
import pytest

from prod_core.data import FeedHealthStatus, MarketDataFeed, SymbolFeedSpec
from prod_core.data.feed import CandleRecord, FeedIntegrityError, timeframe_to_timedelta


def build_candles(count: int, timeframe: str = "1m") -> List[List[float]]:
    """Возвращает последовательность свечей в формате ccxt."""

    base_ts = pd.Timestamp("2024-01-01T00:00:00Z").value // 10**6
    step = timeframe_to_timedelta(timeframe)
    candles: List[List[float]] = []
    price = 100.0
    for i in range(count):
        ts = base_ts + int(step.total_seconds() * 1000 * i)
        candles.append(
            [
                ts,
                price,
                price + 0.5,
                price - 0.5,
                price + 0.2,
                10 + i,
            ]
        )
        price += 0.1
    return candles


class FakeExchange:
    """Минимальная реализация ccxt Exchange для тестов."""

    def __init__(self, book: Dict[Tuple[str, str], List[List[float]]]) -> None:
        self._book = book

    def fetch_ohlcv(self, symbol: str, timeframe: str, since: int | None, limit: int, params: dict | None = None):
        data = self._book[(symbol, timeframe)]
        if since is None:
            return data[:limit]
        filtered = [row for row in data if row[0] >= since]
        return filtered[:limit]

    def milliseconds(self) -> int:
        # возвращаем самую позднюю точку + шаг, чтобы backfill покрывал окно
        latest = max(rows[-1][0] for rows in self._book.values())
        return int(latest + 60_000)

    def close(self) -> None:
        pass


def test_feed_backfill_monotonic() -> None:
    asyncio.run(_test_feed_backfill_monotonic())


async def _test_feed_backfill_monotonic() -> None:
    symbol = "BTC/USDT:USDT"
    timeframe = "1m"
    candles = build_candles(2100, timeframe=timeframe)
    exchange = FakeExchange({(symbol, timeframe): candles})

    spec = SymbolFeedSpec(
        name=symbol,
        type="perp",
        timeframes=(timeframe,),
        primary_timeframe=timeframe,
        backfill_bars=2000,
        min_notional=50,
        max_leverage=3,
        quote_precision=2,
        base_precision=3,
        min_liquidity_usd=1_000_000,
        max_spread_pct=0.1,
        poll_interval_seconds=2.0,
    )
    feed = MarketDataFeed(
        exchange_id="binanceusdm",
        symbols=[spec],
        rest_client=exchange,
        use_websocket=False,
    )

    await feed._backfill_initial()
    snapshot = feed.snapshot()
    frame = snapshot[symbol][timeframe]

    assert len(frame) >= spec.backfill_bars
    assert frame.index.is_monotonic_increasing
    assert feed.status()[symbol][timeframe] == FeedHealthStatus.OK


def test_gap_detection_without_fill_raises() -> None:
    asyncio.run(_test_gap_detection_without_fill_raises())


async def _test_gap_detection_without_fill_raises() -> None:
    symbol = "BTC/USDT:USDT"
    timeframe = "1m"
    candles = build_candles(10, timeframe=timeframe)
    exchange = FakeExchange({(symbol, timeframe): candles})

    spec = SymbolFeedSpec(
        name=symbol,
        type="perp",
        timeframes=(timeframe,),
        primary_timeframe=timeframe,
        backfill_bars=10,
        min_notional=50,
        max_leverage=3,
        quote_precision=2,
        base_precision=3,
        min_liquidity_usd=1_000_000,
        max_spread_pct=0.1,
        poll_interval_seconds=2.0,
    )
    feed = MarketDataFeed(
        exchange_id="binanceusdm",
        symbols=[spec],
        rest_client=exchange,
        use_websocket=False,
        allow_gap_fill=False,
    )

    await feed._backfill_initial()
    buffer = feed._buffers[symbol][timeframe]  # type: ignore[attr-defined]
    expected_delta = timeframe_to_timedelta(timeframe)
    gap_ts = buffer.last_timestamp() + expected_delta * 5  # type: ignore[operator]

    record = CandleRecord(
        ts=gap_ts,
        open=101.0,
        high=101.5,
        low=100.5,
        close=101.2,
        volume=20.0,
        tf=timeframe,
        symbol=symbol,
        source="test",
    )

    with pytest.raises(FeedIntegrityError):
        await feed._append_record(buffer, expected_delta, record)  # type: ignore[attr-defined]


