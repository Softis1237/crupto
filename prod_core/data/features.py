"""Расчёт признаков для стратегий на основе свечного фида."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Final
import pandas as pd

from prod_core.indicators import TechnicalIndicators


@dataclass(slots=True)
class FeatureConfig:
    """Параметры базовых индикаторов."""

    ema_fast: int = 12
    ema_slow: int = 26
    atr_period: int = 14
    returns_lag: int = 1
    volatility_window: int = 30


class FeatureEngineer:
    """Детерминированный конструктор признаков."""

    FEATURE_COLUMNS: Final[tuple[str, ...]] = (
        "ema_fast",
        "ema_slow",
        "atr",
        "return_lag",
        "volatility",
    )

    def __init__(self, indicators: TechnicalIndicators | None = None) -> None:
        self._indicators = indicators or TechnicalIndicators()

    def build(self, candles: pd.DataFrame, config: FeatureConfig | None = None) -> pd.DataFrame:
        """
        Вычисляет признаки по историческим данным без look-ahead.

        Все признаки смещаются на один бар назад, чтобы стратегия не использовала
        незавершённые значения текущей свечи.
        """

        cfg = config or FeatureConfig()
        features = pd.DataFrame(index=candles.index)
        close = candles["close"].astype(float)

        features["ema_fast"] = (
            self._indicators.ema(close, cfg.ema_fast).shift(1)
        )
        features["ema_slow"] = (
            self._indicators.ema(close, cfg.ema_slow).shift(1)
        )
        features["atr"] = (
            self._indicators.atr(
                high=candles["high"],
                low=candles["low"],
                close=close,
                period=cfg.atr_period,
            ).shift(1)
        )
        features["return_lag"] = (
            close.pct_change(cfg.returns_lag).shift(1).fillna(0.0)
        )
        features["volatility"] = (
            close.pct_change().rolling(cfg.volatility_window).std().shift(1).fillna(0.0)
        )

        if "funding_rate" in candles.columns:
            features["funding_rate"] = candles["funding_rate"].astype(float).shift(1).fillna(0.0)

        features = features.dropna()
        return features

    def build_map(
        self,
        candles_map: Dict[str, Dict[str, pd.DataFrame]],
        config: FeatureConfig | None = None,
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """Возвращает словарь признаков {symbol: {timeframe: DataFrame}}."""

        result: Dict[str, Dict[str, pd.DataFrame]] = {}
        for symbol, per_timeframe in candles_map.items():
            result[symbol] = {}
            for timeframe, frame in per_timeframe.items():
                if frame.empty:
                    result[symbol][timeframe] = frame.copy()
                    continue
                result[symbol][timeframe] = self.build(frame, config=config)
        return result

    @staticmethod
    def ensure_no_lookahead(
        candles: pd.DataFrame,
        features: pd.DataFrame,
        config: FeatureConfig | None = None,
        indicators: TechnicalIndicators | None = None,
    ) -> bool:
        """Проверяет, что пересчёт признаков на усечённых данных даёт те же значения."""

        if len(features) < 2:
            return True
        engineer = FeatureEngineer(indicators)
        rebuilt = engineer.build(candles.iloc[:-1], config=config)
        return features.iloc[:-1].equals(rebuilt)

    @staticmethod
    def ensure_map_no_lookahead(
        candles_map: Dict[str, Dict[str, pd.DataFrame]],
        features_map: Dict[str, Dict[str, pd.DataFrame]],
        config: FeatureConfig | None = None,
    ) -> bool:
        """Проверяет, что для всех символов отсутствует look-ahead."""

        for symbol, per_timeframe in features_map.items():
            for timeframe, features in per_timeframe.items():
                candles = candles_map.get(symbol, {}).get(timeframe)
                if candles is None:
                    continue
                if not FeatureEngineer.ensure_no_lookahead(
                    candles=candles,
                    features=features,
                    config=config,
                ):
                    return False
        return True
