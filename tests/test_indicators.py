import numpy as np
import pandas as pd

from prod_core.indicators import TechnicalIndicators


def test_ema_matches_pandas() -> None:
    series = pd.Series([1, 2, 3, 4, 5], dtype=float)
    indicators = TechnicalIndicators()
    ema = indicators.ema(series, 3)
    expected = series.ewm(span=3, adjust=False).mean()
    assert np.allclose(ema.values, expected.values)


def test_atr_behaviour() -> None:
    high = pd.Series([10, 11, 12, 13], dtype=float)
    low = pd.Series([9, 8, 9, 10], dtype=float)
    close = pd.Series([9.5, 10.5, 11.5, 12.5], dtype=float)
    indicators = TechnicalIndicators()
    atr = indicators.atr(high, low, close, period=3)
    assert len(atr) == 4
    assert atr.iloc[-1] > 0


def test_donchian_channels_bounds() -> None:
    high = pd.Series([10, 11, 12, 13, 14], dtype=float)
    low = pd.Series([8, 7, 8, 9, 10], dtype=float)
    indicators = TechnicalIndicators()
    channels = indicators.donchian_channels(high, low, period=3)
    assert set(channels.columns) == {"upper", "lower", "middle"}
    assert (channels["upper"] >= channels["middle"]).all()
    assert (channels["lower"] <= channels["middle"]).all()
