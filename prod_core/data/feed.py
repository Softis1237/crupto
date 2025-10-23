"""Потоковый фид на базе CCXT с WebSocket и REST-фолбэком."""

from __future__ import annotations

import asyncio
import logging
import random
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Any, Callable, Dict, Iterable, List, Optional

import pandas as pd

import ccxt  # type: ignore[import-untyped]

try:
    import ccxt.pro as ccxtpro  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - опциональная зависимость
    ccxtpro = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class FeedIntegrityError(RuntimeError):
    """Выбрасывается при нарушении целостности фида (gap/double)."""


def timeframe_to_timedelta(timeframe: str) -> timedelta:
    """Преобразует строковый таймфрейм CCXT к timedelta."""

    unit = timeframe[-1]
    value = int(timeframe[:-1])
    mapping = {
        "m": timedelta(minutes=value),
        "h": timedelta(hours=value),
        "d": timedelta(days=value),
    }
    if unit not in mapping:
        raise ValueError(f"Неподдерживаемый таймфрейм: {timeframe}")
    return mapping[unit]


def timeframe_to_milliseconds(timeframe: str) -> int:
    """Возвращает длительность таймфрейма в миллисекундах."""

    return int(timeframe_to_timedelta(timeframe).total_seconds() * 1000)


@dataclass(slots=True)
class SymbolFeedSpec:
    """Параметры подписки на символ и список таймфреймов."""

    name: str
    type: str
    timeframes: tuple[str, ...]
    primary_timeframe: str
    backfill_bars: int
    min_notional: float
    max_leverage: float
    quote_precision: int
    base_precision: int
    min_liquidity_usd: float
    max_spread_pct: float
    poll_interval_seconds: float = 5.0


@dataclass(slots=True)
class CandleRecord:
    """Нормализованная запись свечи."""

    ts: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float
    tf: str
    symbol: str
    source: str


class CandleBuffer:
    """Кольцевой буфер свечей на один символ/таймфрейм."""

    def __init__(self, symbol: str, timeframe: str, maxlen: int = 5000) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.maxlen = maxlen
        self._records: "OrderedDict[pd.Timestamp, CandleRecord]" = OrderedDict()

    def __len__(self) -> int:
        return len(self._records)

    def upsert(self, record: CandleRecord) -> None:
        """Добавляет или обновляет свечу, сохраняя упорядоченность."""

        self._records[record.ts] = record
        # OrderedDict не гарантирует сортировку по ключам, поэтому пересоздаём.
        self._records = OrderedDict(sorted(self._records.items(), key=lambda item: item[0]))
        while len(self._records) > self.maxlen:
            self._records.popitem(last=False)

    def last_timestamp(self) -> pd.Timestamp | None:
        try:
            return next(reversed(self._records))
        except StopIteration:
            return None

    def to_frame(self) -> pd.DataFrame:
        """Возвращает DataFrame с индексом времени."""

        if not self._records:
            columns = ["ts", "open", "high", "low", "close", "volume", "tf", "symbol", "source"]
            return pd.DataFrame(columns=columns).set_index("ts")

        rows = [
            {
                "ts": rec.ts,
                "open": rec.open,
                "high": rec.high,
                "low": rec.low,
                "close": rec.close,
                "volume": rec.volume,
                "tf": rec.tf,
                "symbol": rec.symbol,
                "source": rec.source,
            }
            for rec in self._records.values()
        ]
        frame = pd.DataFrame(rows)
        frame.set_index("ts", inplace=True)
        frame.sort_index(inplace=True)
        return frame


class FeedHealthStatus(IntEnum):
    """Уровни здоровья фида."""

    OK = 1
    DEGRADED = 0
    PAUSED = -1


class MarketDataFeed:
    """Загружает исторические данные и поддерживает поток свечей через CCXT."""

    def __init__(
        self,
        exchange_id: str,
        symbols: Iterable[SymbolFeedSpec],
        *,
        rest_client: ccxt.Exchange | None = None,
        use_websocket: bool = True,
        buffer_size: int = 5000,
        health_drift_ms: int = 1500,
        allow_gap_fill: bool = True,
        on_health_change: Callable[[str, str, FeedHealthStatus], None] | None = None,
    ) -> None:
        self.exchange_id = exchange_id
        self.symbols = tuple(symbols)
        self.buffer_size = buffer_size
        self.health_drift_ms = health_drift_ms
        self.allow_gap_fill = allow_gap_fill
        self.on_health_change = on_health_change

        self._rest = rest_client or self._build_rest_client(exchange_id)
        self._use_websocket = use_websocket and ccxtpro is not None
        self._ws: Any | None = None

        self._buffers: Dict[str, Dict[str, CandleBuffer]] = defaultdict(dict)
        self._locks: Dict[tuple[str, str], asyncio.Lock] = {}
        self._status: Dict[tuple[str, str], FeedHealthStatus] = {}
        self._ready: Dict[tuple[str, str], asyncio.Event] = {}
        self._tasks: Dict[tuple[str, str], asyncio.Task[None]] = {}
        self._stop_event = asyncio.Event()

        for spec in self.symbols:
            for timeframe in spec.timeframes:
                key = (spec.name, timeframe)
                self._buffers[spec.name][timeframe] = CandleBuffer(spec.name, timeframe, maxlen=buffer_size)
                self._locks[key] = asyncio.Lock()
                self._status[key] = FeedHealthStatus.PAUSED
                self._ready[key] = asyncio.Event()

    @staticmethod
    def _build_rest_client(exchange_id: str) -> ccxt.Exchange:
        try:
            exchange_class = getattr(ccxt, exchange_id)
        except AttributeError as exc:  # pragma: no cover - конфигурационная ошибка
            raise ValueError(f"Неизвестный exchange_id={exchange_id}") from exc
        return exchange_class({"enableRateLimit": True})

    async def start(self) -> None:
        """Инициирует backfill и запускает подписки."""

        self._stop_event.clear()
        await self._backfill_initial()
        if self._use_websocket and ccxtpro is not None:
            ws_class = getattr(ccxtpro, self.exchange_id, None)
            if ws_class is None:
                logger.warning("ccxt.pro не поддерживает %s — переходим на REST-поллинг.", self.exchange_id)
                self._use_websocket = False
            else:
                self._ws = ws_class({"enableRateLimit": True})

        for spec in self.symbols:
            for timeframe in spec.timeframes:
                key = (spec.name, timeframe)
                task = asyncio.create_task(self._subscription_loop(spec, timeframe), name=f"feed-{spec.name}-{timeframe}")
                self._tasks[key] = task

    async def stop(self) -> None:
        """Останавливает подписки и закрывает клиенты."""

        self._stop_event.set()
        for task in list(self._tasks.values()):
            task.cancel()
        for key, task in list(self._tasks.items()):
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:  # pragma: no cover - логирование нарушения
                logger.exception("Ошибка завершения задачи фида %s/%s", *key)
        self._tasks.clear()

        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # pragma: no cover - закрытие ws
                logger.exception("Ошибка закрытия ccxt.pro соединения")
            finally:
                self._ws = None

        if hasattr(self._rest, "close"):
            await asyncio.to_thread(self._rest.close)

    async def __aenter__(self) -> MarketDataFeed:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()

    async def _backfill_initial(self) -> None:
        """Загружает историю для каждого символа и таймфрейма."""

        tasks = [self._backfill_symbol(spec, timeframe) for spec in self.symbols for timeframe in spec.timeframes]
        await asyncio.gather(*tasks)

    async def _backfill_symbol(self, spec: SymbolFeedSpec, timeframe: str) -> None:
        key = (spec.name, timeframe)
        limit = max(spec.backfill_bars, 2000)
        timeframe_ms = timeframe_to_milliseconds(timeframe)
        now_ms = self._rest.milliseconds()
        since = now_ms - timeframe_ms * (limit + 2)
        fetched = 0

        while fetched < limit and not self._stop_event.is_set():
            batch_limit = min(1000, limit - fetched)
            candles = await self._fetch_ohlcv(spec.name, timeframe, limit=batch_limit, since=since)
            if not candles:
                break
            await self._ingest_records(spec, timeframe, candles, source="rest")
            fetched = len(self._buffers[spec.name][timeframe])
            since = int(candles[-1].ts.timestamp() * 1000) + timeframe_ms
            if len(candles) < batch_limit:
                break

        self._ready[key].set()
        self._set_status(spec.name, timeframe, FeedHealthStatus.OK)
        logger.info(
            "Backfill завершён: %s %s (%s баров)",
            spec.name,
            timeframe,
            len(self._buffers[spec.name][timeframe]),
        )

    async def _subscription_loop(self, spec: SymbolFeedSpec, timeframe: str) -> None:
        """Основной цикл получения новых свечей."""

        key = (spec.name, timeframe)
        poll_interval = max(1.0, spec.poll_interval_seconds)
        retry_delay = 1.0

        while not self._stop_event.is_set():
            try:
                if self._use_websocket and self._ws is not None:
                    await self._consume_ws(spec, timeframe)
                else:
                    await self._poll_once(spec, timeframe)
                    await asyncio.sleep(poll_interval)
                retry_delay = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "Ошибка подписки %s/%s: %s. Переход к REST-поллингу.",
                    spec.name,
                    timeframe,
                    exc,
                )
                self._use_websocket = False
                self._set_status(spec.name, timeframe, FeedHealthStatus.DEGRADED)
                await asyncio.sleep(min(30.0, retry_delay))
                retry_delay = min(30.0, retry_delay * 2)

        self._status[key] = FeedHealthStatus.PAUSED

    async def _consume_ws(self, spec: SymbolFeedSpec, timeframe: str) -> None:
        """Получение свечей через ccxt.pro."""

        assert self._ws is not None
        while not self._stop_event.is_set():
            data = await self._ws.watch_ohlcv(spec.name, timeframe)
            candles = self._normalize(data, spec.name, timeframe, source="ws")
            await self._ingest_records(spec, timeframe, candles, source="ws")

    async def _poll_once(self, spec: SymbolFeedSpec, timeframe: str) -> None:
        """REST-поллинг последней свечи (fallback)."""

        buffer = self._buffers[spec.name][timeframe]
        last_ts = buffer.last_timestamp()
        since = None if last_ts is None else int(last_ts.timestamp() * 1000)
        candles = await self._fetch_ohlcv(spec.name, timeframe, limit=2, since=since)
        if not candles:
            return
        await self._ingest_records(spec, timeframe, candles, source="rest")

    async def _fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        *,
        limit: int,
        since: int | None,
    ) -> List[CandleRecord]:
        """Обёртка над ccxt.fetch_ohlcv с back-off."""

        def call() -> List[list[Any]]:
            params: Dict[str, Any] = {"limit": limit}
            return self._rest.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit, params=params)

        retries = 0
        delay = 1.0
        while True:
            try:
                raw = await asyncio.to_thread(call)
                return self._normalize(raw, symbol, timeframe, source="rest")
            except ccxt.RateLimitExceeded as exc:  # pragma: no cover - зависит от биржи
                wait_for = min(60.0, delay * (2**retries))
                logger.warning("Rate limit для %s/%s. Повтор через %.2fs", symbol, timeframe, wait_for)
                await asyncio.sleep(wait_for)
                retries += 1
            except ccxt.NetworkError as exc:
                wait_for = min(60.0, delay * (2**retries))
                logger.warning("Сетевая ошибка %s/%s: %s. Retrying через %.2fs", symbol, timeframe, exc, wait_for)
                await asyncio.sleep(wait_for + random.uniform(0, 1))
                retries += 1

    async def _ingest_records(
        self,
        spec: SymbolFeedSpec,
        timeframe: str,
        records: List[CandleRecord],
        *,
        source: str,
    ) -> None:
        """Обновляет буфер, контролируя дубликаты и разрывы."""

        if not records:
            return
        key = (spec.name, timeframe)
        async with self._locks[key]:
            buffer = self._buffers[spec.name][timeframe]
            expected_delta = timeframe_to_timedelta(timeframe)
            for record in records:
                await self._append_record(buffer, expected_delta, record)
            self._ready[key].set()

    async def _append_record(
        self,
        buffer: CandleBuffer,
        expected_delta: timedelta,
        record: CandleRecord,
    ) -> None:
        last_ts = buffer.last_timestamp()

        if last_ts is not None:
            delta = record.ts - last_ts
            if delta < expected_delta * 0.5:
                # дубликат — просто перезапишем последнюю свечу
                buffer.upsert(record)
                self._update_health(record.symbol, record.tf, record.ts)
                return
            if delta > expected_delta * 1.5:
                logger.warning(
                    "Обнаружен разрыв %s/%s: %s → %s (Δ=%.2f мин)",
                    record.symbol,
                    record.tf,
                    last_ts,
                    record.ts,
                    delta.total_seconds() / 60,
                )
                if not self.allow_gap_fill:
                    raise FeedIntegrityError(f"Gap в свечах {record.symbol}/{record.tf} длиной {delta}.")
                await self._fill_gap(record.symbol, record.tf, last_ts, record.ts, expected_delta)

        buffer.upsert(record)
        self._update_health(record.symbol, record.tf, record.ts)

    async def _fill_gap(
        self,
        symbol: str,
        timeframe: str,
        start: pd.Timestamp,
        end: pd.Timestamp,
        expected_delta: timedelta,
    ) -> None:
        """Доскачивает пропущенные бары (gap-policy)."""

        timeframe_ms = timeframe_to_milliseconds(timeframe)
        since = int(start.timestamp() * 1000 + timeframe_ms)
        while since < int(end.timestamp() * 1000):
            missing = await self._fetch_ohlcv(symbol, timeframe, limit=5, since=since)
            if not missing:
                break
            spec = SymbolFeedSpec(
                name=symbol,
                type="spot",
                timeframes=(timeframe,),
                primary_timeframe=timeframe,
                backfill_bars=len(missing),
                min_notional=1.0,
                max_leverage=1.0,
                quote_precision=0,
                base_precision=0,
                min_liquidity_usd=1.0,
                max_spread_pct=1.0,
            )
            await self._ingest_records(spec, timeframe, missing, source="rest-gap")
            since = int(missing[-1].ts.timestamp() * 1000 + timeframe_ms)

    def _normalize(
        self,
        payload: Iterable[Iterable[Any]],
        symbol: str,
        timeframe: str,
        *,
        source: str,
    ) -> List[CandleRecord]:
        """Преобразует данные ccxt к CandleRecord."""

        records: List[CandleRecord] = []
        for item in payload:
            timestamp_ms, open_, high, low, close, volume = item[:6]
            ts = pd.Timestamp(timestamp_ms, unit="ms", tz=timezone.utc)
            records.append(
                CandleRecord(
                    ts=ts,
                    open=float(open_),
                    high=float(high),
                    low=float(low),
                    close=float(close),
                    volume=float(volume),
                    tf=timeframe,
                    symbol=symbol,
                    source=source,
                )
            )
        return records

    def _update_health(self, symbol: str, timeframe: str, ts: pd.Timestamp) -> None:
        drift = datetime.now(timezone.utc) - ts
        drift_ms = abs(drift.total_seconds() * 1000)
        status = FeedHealthStatus.OK if drift_ms <= self.health_drift_ms else FeedHealthStatus.DEGRADED
        self._set_status(symbol, timeframe, status)

    def _set_status(self, symbol: str, timeframe: str, status: FeedHealthStatus) -> None:
        key = (symbol, timeframe)
        current = self._status.get(key)
        if current == status:
            return
        self._status[key] = status
        if self.on_health_change:
            try:
                self.on_health_change(symbol, timeframe, status)
            except Exception:  # pragma: no cover - обработка пользовательского хука
                logger.exception("on_health_change вызвал исключение для %s/%s", symbol, timeframe)

    def snapshot(self, *, min_bars: int | None = None) -> Dict[str, Dict[str, pd.DataFrame]]:
        """Возвращает копию буферов с фильтром по количеству баров."""

        result: Dict[str, Dict[str, pd.DataFrame]] = {}
        for symbol, timeframes in self._buffers.items():
            for timeframe, buffer in timeframes.items():
                if min_bars is not None and len(buffer) < min_bars:
                    continue
                result.setdefault(symbol, {})[timeframe] = buffer.to_frame()
        return result

    def status(self) -> Dict[str, Dict[str, FeedHealthStatus]]:
        """Возвращает словарь статусов по символам и таймфреймам."""

        stats: Dict[str, Dict[str, FeedHealthStatus]] = {}
        for (symbol, timeframe), status in self._status.items():
            stats.setdefault(symbol, {})[timeframe] = status
        return stats

    async def wait_ready(self, symbol: str, timeframe: str, *, timeout: float | None = None) -> bool:
        """Ожидает backfill для указанного символа и таймфрейма."""

        key = (symbol, timeframe)
        event = self._ready[key]
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
