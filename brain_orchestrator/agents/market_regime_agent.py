"""Агент определения рыночного режима."""

from __future__ import annotations

import time
from typing import Dict, Tuple

import pandas as pd

from brain_orchestrator.regimes import MarketRegime
from brain_orchestrator.tools import ToolRegistry
from brain_orchestrator.tools.base import ToolContext
from prod_core.monitor.telemetry import TelemetryExporter


class MarketRegimeAgent:
    """Использует инструменты для расчёта признаков и классификации режима."""

    def __init__(self, registry: ToolRegistry, telemetry: TelemetryExporter) -> None:
        self.registry = registry
        self.telemetry = telemetry

    def run(
        self,
        context: ToolContext,
        candles: pd.DataFrame,
    ) -> Tuple[Dict[str, Dict[str, pd.DataFrame]], MarketRegime]:
        """Возвращает словарь признаков по символам и режим."""

        start = time.perf_counter()
        feature_tool = self.registry.resolve("calc_features")
        features = feature_tool.execute(context, candles=candles)
        latency = time.perf_counter() - start
        self.telemetry.record_agent_tool("market_regime", "calc_features", 1, latency)

        start = time.perf_counter()
        regime_tool = self.registry.resolve("classify_regime")
        primary_features = self._select_primary_features(features, context)
        regime = regime_tool.execute(context, features=primary_features)
        latency = time.perf_counter() - start
        self.telemetry.record_agent_tool("market_regime", "classify_regime", 1, latency)
        self.telemetry.record_regime(regime.value)
        return features, regime

    @staticmethod
    def _select_primary_features(
        features_map: Dict[str, Dict[str, pd.DataFrame]],
        context: ToolContext,
    ) -> pd.DataFrame:
        symbol_features = features_map.get(context.symbol, {})
        timeframe = context.timeframe or next(iter(symbol_features.keys()), None)
        if timeframe is None:
            return pd.DataFrame()
        return symbol_features.get(timeframe, pd.DataFrame())
