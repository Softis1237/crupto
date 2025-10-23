"""Утилиты валидации результатов агентов."""

from __future__ import annotations

import pandas as pd

from prod_core.strategies import StrategyPlan


def validate_features(features: pd.DataFrame) -> None:
    """Поднимает ValueError при некорректных признаках."""

    required = {"ema_fast", "ema_slow", "atr", "return_lag", "volatility"}
    missing = required.difference(features.columns)
    if missing:
        raise ValueError(f"Отсутствуют признаки: {sorted(missing)}")
    if not features.index.is_monotonic_increasing:
        raise ValueError("Индекс признаков должен быть монотонным.")


def validate_plan(plan: StrategyPlan) -> None:
    """Проверяет, что план имеет валидный риск и размер."""

    if plan.size <= 0:
        raise ValueError("Размер позиции должен быть > 0.")
    if plan.risk_pct <= 0:
        raise ValueError("Доля риска должна быть > 0.")
