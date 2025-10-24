"""Стратегия реверсии по экстремальным фондингам."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from brain_orchestrator.regimes import MarketRegime
from prod_core.strategies.base import StrategySignal, TradingStrategy


@dataclass(slots=True)
class FundingReversionConfig:
    """Пороговые параметры для входа против перекошенного фондинга."""

    funding_threshold: float = 0.001
    min_confidence: float = 0.5


class FundingReversionStrategy(TradingStrategy):
    """Использует перекос фондирования для реверсивных сделок."""

    def __init__(self, config: Optional[FundingReversionConfig] = None) -> None:
        super().__init__(
            name="funding_rev",
            timeframe="1h",
            min_hold_bars=4,
            supported_regimes=(
                MarketRegime.RANGE_LOWVOL,
                MarketRegime.RANGE_HIGHVOL,
                MarketRegime.PANIC,
            ),
        )
        self._config = config or FundingReversionConfig()

    def _generate(self, candles: pd.DataFrame, features: pd.DataFrame) -> list[StrategySignal]:
        """Проверяет знак фондирования и строит реверсивный сигнал."""

        funding = features.get("funding_rate")
        if funding is None or len(funding) == 0:
            return []

        last_idx = funding.index[-1]
        funding_value = float(funding.iloc[-1])
        if abs(funding_value) < self._config.funding_threshold:
            return []

        timestamp = last_idx.to_pydatetime()
        side = "long" if funding_value > 0 else "short"
        confidence = max(
            self._config.min_confidence,
            min(0.9, abs(funding_value) * 50),
        )

        return [
            StrategySignal(
                timestamp=timestamp,
                side=side,
                confidence=confidence,
                metadata={"funding_rate": funding_value},
            )
        ]
