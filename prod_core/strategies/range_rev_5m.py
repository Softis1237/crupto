"""Стратегия возврата к среднему на 5M таймфрейме."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from brain_orchestrator.regimes import MarketRegime
from prod_core.strategies.base import StrategySignal, TradingStrategy


@dataclass(slots=True)
class RangeReversionConfig:
    """Настройки поиска отклонений от средней."""

    deviation_threshold: float = 0.0
    ema_gap_threshold: float = 1.0


class RangeReversion5MStrategy(TradingStrategy):
    """Ищет отклонения цены в боковом рынке для mean-reversion."""

    def __init__(self, config: Optional[RangeReversionConfig] = None) -> None:
        super().__init__(
            name="range_rev_5m",
            timeframe="5m",
            min_hold_bars=2,
            supported_regimes=(
                MarketRegime.RANGE_LOWVOL,
                MarketRegime.RANGE_HIGHVOL,
            ),
        )
        self._config = config or RangeReversionConfig()

    def _generate(self, candles: pd.DataFrame, features: pd.DataFrame) -> list[StrategySignal]:
        """Выводит сигнал возврата при отклонении цены от EMA."""

        signals: list[StrategySignal] = []
        close = candles["close"]
        ema_fast = features["ema_fast"]
        ema_slow = features["ema_slow"]
        last_idx = close.index[-1]
        last_price = float(close.iloc[-1])
        anchor = float(ema_slow.iloc[-1])
        deviation = (last_price - anchor) / anchor
        ema_gap = float(ema_fast.iloc[-1] - ema_slow.iloc[-1]) / anchor

        if abs(deviation) < self._config.deviation_threshold:
            return signals
        if abs(ema_gap) > self._config.ema_gap_threshold:
            return signals

        timestamp = last_idx.to_pydatetime()
        side = "short" if deviation > 0 else "long"
        confidence = min(0.85, 0.55 + abs(deviation) * 10)

        signals.append(
            StrategySignal(
                timestamp=timestamp,
                side=side,
                confidence=confidence,
                metadata={
                    "deviation": deviation,
                    "ema_gap": ema_gap,
                },
            )
        )
        return signals
