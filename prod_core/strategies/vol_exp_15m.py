"""Стратегия экспансии волатильности на 15M таймфрейме."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from brain_orchestrator.regimes import MarketRegime
from prod_core.strategies.base import StrategySignal, TradingStrategy


@dataclass(slots=True)
class VolatilityExpansionConfig:
    """Параметры детектора импульса."""

    vol_threshold: float = 0.004
    min_confidence: float = 0.45


class VolatilityExpansion15MStrategy(TradingStrategy):
    """Выявляет всплески волатильности с подтверждением импульса."""

    def __init__(self, config: Optional[VolatilityExpansionConfig] = None) -> None:
        super().__init__(
            name="vol_exp_15m",
            timeframe="15m",
            min_hold_bars=4,
            supported_regimes=(
                MarketRegime.TREND_UP,
                MarketRegime.TREND_DOWN,
                MarketRegime.RANGE_HIGHVOL,
            ),
        )
        self._config = config or VolatilityExpansionConfig()

    def _generate(self, candles: pd.DataFrame, features: pd.DataFrame) -> list[StrategySignal]:
        """Строит сигнал при разрастании волатильности и подтверждении импульса."""

        signals: list[StrategySignal] = []
        close = candles["close"]
        vol = features["volatility"]
        returns = features["return_lag"]

        if len(vol) < 2 or len(returns) < 2:
            return signals

        last_idx = close.index[-1]
        last_return = float(returns.iloc[-1])
        last_vol = float(vol.iloc[-1])
        prev_vol = float(vol.iloc[-2])

        vol_spike = last_vol > self._config.vol_threshold and last_vol > prev_vol

        if not vol_spike:
            return signals

        timestamp = last_idx.to_pydatetime()
        side = "long" if last_return > 0 else "short"
        confidence = min(0.9, max(self._config.min_confidence, abs(last_return) * 5))

        signals.append(
            StrategySignal(
                timestamp=timestamp,
                side=side,
                confidence=confidence,
                metadata={"volatility": last_vol, "return_lag": last_return},
            )
        )
        return signals
