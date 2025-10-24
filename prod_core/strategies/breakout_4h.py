"""Стратегия пробоя диапазона на 4H таймфрейме."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from brain_orchestrator.regimes import MarketRegime
from prod_core.indicators import TechnicalIndicators
from prod_core.strategies.base import StrategySignal, TradingStrategy


@dataclass(slots=True)
class BreakoutConfig:
    """Параметры канала Дончиана для пробойной стратегии."""

    channel_period: int = 10
    min_breakout_factor: float = 0.0003  # 0.1% от цены


class Breakout4HStrategy(TradingStrategy):
    """Детерминированная пробойная стратегия на 4H."""

    def __init__(self, indicators: Optional[TechnicalIndicators] = None, config: BreakoutConfig | None = None) -> None:
        super().__init__(
            name="breakout_4h",
            timeframe="4h",
            min_hold_bars=3,
            supported_regimes=(MarketRegime.TREND_UP, MarketRegime.TREND_DOWN),
        )
        self._indicators = indicators or TechnicalIndicators()
        self._config = config or BreakoutConfig()

    def _generate(self, candles: pd.DataFrame, features: pd.DataFrame) -> list[StrategySignal]:
        """Строит сигналы на основе пробоя каналов Дончиана."""

        signals: list[StrategySignal] = []
        donchian = self._indicators.donchian_channels(candles["high"], candles["low"], self._config.channel_period)
        close = candles["close"]
        last_idx = close.index[-1]
        last_price = float(close.iloc[-1])
        upper = float(donchian["upper"].iloc[-2])
        lower = float(donchian["lower"].iloc[-2])
        atr = float(features["atr"].iloc[-1]) if "atr" in features.columns else None

        breakout_up = last_price - upper > self._config.min_breakout_factor * last_price
        breakout_down = lower - last_price > self._config.min_breakout_factor * last_price

        timestamp = last_idx.to_pydatetime()
        if breakout_up:
            signals.append(
                StrategySignal(
                    timestamp=timestamp,
                    side="long",
                    confidence=0.7,
                    stop_loss=last_price - (atr or 0.0),
                    take_profit=last_price + 2 * (atr or 0.0),
                    metadata={"upper_channel": upper},
                )
            )
        if breakout_down:
            signals.append(
                StrategySignal(
                    timestamp=timestamp,
                    side="short",
                    confidence=0.7,
                    stop_loss=last_price + (atr or 0.0),
                    take_profit=last_price - 2 * (atr or 0.0),
                    metadata={"lower_channel": lower},
                )
            )
        return signals
