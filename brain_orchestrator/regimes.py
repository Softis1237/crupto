"""Определение рыночных режимов на основе признаков."""

from __future__ import annotations

from enum import Enum, IntEnum

import pandas as pd


class MarketRegime(IntEnum):
    """Коды рыночных режимов, используемые в телеметрии."""

    TREND_UP = 1
    TREND_DOWN = 2
    RANGE_LOWVOL = 3
    RANGE_HIGHVOL = 4
    PANIC = 5


class RegimeDetector:
    """Простая эвристика определения режима."""

    def detect(self, features: pd.DataFrame) -> MarketRegime:
        """Возвращает текущий режим на основе последней строки признаков."""

        if features.empty:
            return MarketRegime.RANGE_LOWVOL
        row = features.iloc[-1]
        ema_fast = float(row.get("ema_fast", 0.0))
        ema_slow = float(row.get("ema_slow", 0.0))
        volatility = float(row.get("volatility", 0.0))
        returns = float(row.get("return_lag", 0.0))

        if volatility > 0.04 and returns < -0.02:
            return MarketRegime.PANIC
        if ema_fast > ema_slow * 1.001:
            return MarketRegime.TREND_UP
        if ema_fast < ema_slow * 0.999:
            return MarketRegime.TREND_DOWN
        if volatility > 0.02:
            return MarketRegime.RANGE_HIGHVOL
        return MarketRegime.RANGE_LOWVOL
