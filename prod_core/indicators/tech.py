"""Библиотека базовых технических индикаторов."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(slots=True)
class RollingConfig:
    """Универсальная конфигурация оконных индикаторов."""

    period: int
    min_periods: int | None = None


class TechnicalIndicators:
    """Детерминированные реализации популярных индикаторов."""

    def ema(self, series: pd.Series, period: int) -> pd.Series:
        """Экспоненциальное скользящее среднее."""

        return series.ewm(span=period, adjust=False).mean()

    def atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        """Average True Range по Уайлдеру."""

        tr = self.true_range(high=high, low=low, close=close)
        return tr.rolling(window=period, min_periods=1).mean()

    @staticmethod
    def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """Истинный диапазон для ATR."""

        prev_close = close.shift(1)
        components = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        )
        return components.max(axis=1)

    def donchian_channels(self, high: pd.Series, low: pd.Series, period: int) -> pd.DataFrame:
        """Верхняя и нижняя границы канала Дончиана."""

        upper = high.rolling(window=period, min_periods=1).max()
        lower = low.rolling(window=period, min_periods=1).min()
        middle = (upper + lower) / 2
        return pd.DataFrame({"upper": upper, "lower": lower, "middle": middle}, index=high.index)

    def rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index по Уайлдеру."""

        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50.0)

    def volatility(self, series: pd.Series, window: int) -> pd.Series:
        """Стандартное отклонение доходностей."""

        returns = series.pct_change()
        return returns.rolling(window=window, min_periods=1).std()

    def normalize(self, series: pd.Series) -> pd.Series:
        """Min-Max нормировка для облегчения работы стратегий."""

        min_val = series.min()
        max_val = series.max()
        if np.isclose(max_val, min_val):
            return pd.Series(np.zeros_like(series), index=series.index)
        return (series - min_val) / (max_val - min_val)

    @staticmethod
    def ensure_consistency(series_list: Iterable[pd.Series]) -> bool:
        """Проверяет совместимость индексов у набора временных рядов."""

        indices = [series.index for series in series_list]
        if not indices:
            return True
        first = indices[0]
        return all(first.equals(other) for other in indices[1:])
