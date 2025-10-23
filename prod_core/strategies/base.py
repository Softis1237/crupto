"""Базовые сущности стратегий и интерфейсы построения сигналов."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Final, Literal, Protocol

import pandas as pd

from brain_orchestrator.regimes import MarketRegime

SignalSide = Literal["long", "short", "flat"]


@dataclass(slots=True)
class StrategySignal:
    """Сырые сигналы, рассчитанные стратегией."""

    timestamp: datetime
    side: SignalSide
    confidence: float
    stop_loss: float | None = None
    take_profit: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StrategyPlan:
    """План действий после обработки риском и портфелем."""

    signal: StrategySignal
    size: float
    risk_pct: float
    valid_until: datetime


class PositionSizer(Protocol):
    """Протокол сайзера, используемого стратегией."""

    def __call__(self, signal: StrategySignal, atr: float | None) -> float:
        """Возвращает размер позиции в контрактах."""


class TradingStrategy:
    """Абстрактный класс для всех детерминированных стратегий."""

    name: Final[str]
    timeframe: Final[str]
    min_hold_bars: Final[int]
    supported_regimes: tuple[MarketRegime, ...]

    def __init__(
        self,
        name: str,
        timeframe: str,
        min_hold_bars: int,
        supported_regimes: tuple[MarketRegime, ...],
    ) -> None:
        self.name = name
        self.timeframe = timeframe
        self.min_hold_bars = min_hold_bars
        self.supported_regimes = supported_regimes

    def generate_signals(
        self,
        candles: pd.DataFrame,
        features: pd.DataFrame,
        regime: MarketRegime,
    ) -> list[StrategySignal]:
        """Генерирует детерминированный набор сигналов."""

        if regime not in self.supported_regimes:
            return []
        return self._generate(candles, features)

    def _generate(self, candles: pd.DataFrame, features: pd.DataFrame) -> list[StrategySignal]:
        """Реализация в дочерних классах."""

        raise NotImplementedError

    def build_plan(
        self,
        signal: StrategySignal,
        atr: float | None,
        sizer: PositionSizer,
        lifetime: timedelta,
        risk_pct: float,
    ) -> StrategyPlan:
        """Формирует план исполнения, используя риск-параметры."""

        size = sizer(signal, atr)
        valid_until = signal.timestamp + lifetime
        return StrategyPlan(signal=signal, size=size, risk_pct=risk_pct, valid_until=valid_until)

    def should_skip(self, last_exit: datetime | None, now: datetime) -> bool:
        """Проверяет выдержан ли минимальный холд."""

        if last_exit is None:
            return False
        bars_elapsed = (now - last_exit) / self._bar_duration()
        return bars_elapsed < self.min_hold_bars

    def _bar_duration(self) -> timedelta:
        """Конвертирует таймфрейм стратегии в timedelta."""

        unit = self.timeframe[-1].lower()
        value = int(self.timeframe[:-1])
        mapping = {
            "m": timedelta(minutes=value),
            "h": timedelta(hours=value),
            "d": timedelta(days=value),
        }
        if unit not in mapping:
            msg = f"Неподдерживаемый таймфрейм {self.timeframe}"
            raise ValueError(msg)
        return mapping[unit]
