"""Синтетический фид для тестов и CI."""

from __future__ import annotations

import asyncio
import random
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Iterable, Tuple

import pandas as pd

from .feed import FeedHealthStatus, SymbolFeedSpec, timeframe_to_timedelta


class MockMarketDataFeed:
    """Генерирует детерминированные свечи для имитации рынка."""

    def __init__(
        self,
        *,
        symbols: Iterable[SymbolFeedSpec],
        seed: int | None = 12345,
    ) -> None:
        self.symbols = tuple(symbols)
        self._rng = random.Random(seed)

        self._buffers: Dict[str, Dict[str, pd.DataFrame]] = defaultdict(dict)
        self._ready: Dict[Tuple[str, str], asyncio.Event] = {}
        self._status: Dict[Tuple[str, str], FeedHealthStatus] = {}
        self._last_price: Dict[Tuple[str, str], float] = {}
        self._last_ts: Dict[Tuple[str, str], pd.Timestamp] = {}
        self._max_bars: Dict[Tuple[str, str], int] = {}
        self._poll_interval: Dict[Tuple[str, str], float] = {}
        self._phase: Dict[Tuple[str, str], int] = {}

        self._running = False
        self._producer_task: asyncio.Task[None] | None = None

        self._initialize_buffers()

    def _initialize_buffers(self) -> None:
        """Заполняет стартовые свечи с наклонным трендом и шумом."""

        now = datetime.now(timezone.utc)
        for spec in self.symbols:
            base_price = self._rng.uniform(50, 200)
            drift = self._rng.uniform(-0.2, 0.3)
            for timeframe in spec.timeframes:
                key = (spec.name, timeframe)
                delta = timeframe_to_timedelta(timeframe)
                periods = max(10, spec.backfill_bars)
                index = pd.date_range(
                    end=now,
                    periods=periods,
                    freq=delta,
                    tz=timezone.utc,
                )
                prices = []
                price = base_price
                shock_start = max(5, periods - 40)
                for idx, _ in enumerate(index):
                    if idx < shock_start:
                        step = self._rng.uniform(-0.0015, 0.0035) + drift * 0.01
                        price = max(1.0, price * (1 + step))
                    else:
                        phase = idx - shock_start
                        spike = 0.015 + 0.003 * phase
                        if phase % 2 == 0:
                            price = max(1.0, price * (1 + spike))
                        else:
                            price = max(1.0, price * (1 - spike * 0.55))
                    prices.append(price)

                closes = pd.Series(prices, index=index)
                opens = closes.shift(1).fillna(closes.iloc[0])
                highs = pd.concat([opens, closes], axis=1).max(axis=1) + abs(drift) * 0.5
                lows = pd.concat([opens, closes], axis=1).min(axis=1) - abs(drift) * 0.5
                volumes = []
                for idx, ts in enumerate(index):
                    if idx < shock_start:
                        volumes.append(self._rng.uniform(8_000, 18_000))
                    else:
                        phase = idx - shock_start + 1
                        volumes.append(self._rng.uniform(18_000, 35_000) * (1 + 0.05 * phase))
                volumes = pd.Series(volumes, index=index)

                frame = pd.DataFrame(
                    {
                        "open": opens,
                        "high": highs,
                        "low": lows,
                        "close": closes,
                        "volume": volumes,
                        "tf": timeframe,
                        "symbol": spec.name,
                        "source": "mock",
                    }
                )
                frame.index.name = "ts"

                self._buffers[spec.name][timeframe] = frame
                self._last_price[key] = float(closes.iloc[-1])
                self._last_ts[key] = index[-1]
                self._max_bars[key] = max(20, spec.backfill_bars)
                poll = max(0.1, min(1.0, spec.poll_interval_seconds))
                self._poll_interval[key] = poll
                self._phase[key] = 0

                event = asyncio.Event()
                event.set()
                self._ready[key] = event
                self._status[key] = FeedHealthStatus.OK

    async def __aenter__(self) -> MockMarketDataFeed:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._producer_task = asyncio.create_task(self._produce_loop())

    async def stop(self) -> None:
        self._running = False
        if self._producer_task is not None:
            self._producer_task.cancel()
            try:
                await self._producer_task
            except asyncio.CancelledError:
                pass
            self._producer_task = None

    async def _produce_loop(self) -> None:
        """Добавляет новые свечи для каждого символа/таймфрейма."""

        try:
            while self._running:
                await asyncio.sleep(0.2)
                for spec in self.symbols:
                    for timeframe in spec.timeframes:
                        key = (spec.name, timeframe)
                        await self._append_candle(spec.name, timeframe)
        except asyncio.CancelledError:
            raise

    async def _append_candle(self, symbol: str, timeframe: str) -> None:
        key = (symbol, timeframe)
        delta = timeframe_to_timedelta(timeframe)
        poll = self._poll_interval[key]
        if poll > 0.2:
            # имитируем редкие обновления, пропуская циклы
            if self._rng.random() < 0.5:
                return

        last_ts = self._last_ts[key]
        next_ts = last_ts + delta
        last_price = self._last_price[key]

        phase = self._phase.get(key, 0)
        if phase % 2 == 0:
            spike = 0.018 + 0.003 * (phase % 6)
        else:
            spike = -0.010 * (1 + 0.1 * (phase % 5))
        close = max(0.5, last_price * (1 + spike))
        open_ = last_price
        high = max(open_, close) * (1 + abs(spike) * 0.4)
        low = min(open_, close) * (1 - abs(spike) * 0.4)
        volume = self._rng.uniform(15_000, 32_000) * (1 + abs(spike) * 5)

        frame = self._buffers[symbol][timeframe]
        new_row = pd.DataFrame(
            {
                "open": [open_],
                "high": [high],
                "low": [low],
                "close": [close],
                "volume": [volume],
                "tf": [timeframe],
                "symbol": [symbol],
                "source": ["mock"],
            },
            index=pd.Index([next_ts], name="ts"),
        )
        self._buffers[symbol][timeframe] = pd.concat([frame, new_row])
        if len(self._buffers[symbol][timeframe]) > self._max_bars[key]:
            self._buffers[symbol][timeframe] = self._buffers[symbol][timeframe].iloc[-self._max_bars[key] :]

        self._last_price[key] = close
        self._last_ts[key] = next_ts
        self._status[key] = FeedHealthStatus.OK
        self._phase[key] = phase + 1

    def snapshot(self, *, min_bars: int | None = None) -> Dict[str, Dict[str, pd.DataFrame]]:
        """Возвращает копию буферов, аналогично реальному фиду."""

        result: Dict[str, Dict[str, pd.DataFrame]] = {}
        for symbol, timeframes in self._buffers.items():
            for timeframe, frame in timeframes.items():
                if min_bars is not None and len(frame) < min_bars:
                    continue
                result.setdefault(symbol, {})[timeframe] = frame.copy()
        return result

    def status(self) -> Dict[str, Dict[str, FeedHealthStatus]]:
        stats: Dict[str, Dict[str, FeedHealthStatus]] = {}
        for (symbol, timeframe), status in self._status.items():
            stats.setdefault(symbol, {})[timeframe] = status
        return stats

    async def wait_ready(self, symbol: str, timeframe: str, *, timeout: float | None = None) -> bool:
        event = self._ready[(symbol, timeframe)]
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def __repr__(self) -> str:
        return f"MockMarketDataFeed(symbols={len(self.symbols)})"
