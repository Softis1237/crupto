import pandas as pd

from prod_core.data.features import FeatureEngineer


def make_candles(rows: int = 50) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="15min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": [100 + i * 0.1 for i in range(rows)],
            "high": [100.5 + i * 0.1 for i in range(rows)],
            "low": [99.5 + i * 0.1 for i in range(rows)],
            "close": [100.2 + i * 0.1 for i in range(rows)],
            "volume": [10 + i for i in range(rows)],
        },
        index=index,
    )
    return frame


def test_features_no_lookahead() -> None:
    candles = make_candles()
    engineer = FeatureEngineer()
    features = engineer.build(candles)
    assert FeatureEngineer.ensure_no_lookahead(candles, features)


def test_build_map_returns_dict() -> None:
    candles_map = {"BTC/USDT:USDT": {"15m": make_candles()}}
    engineer = FeatureEngineer()
    features_map = engineer.build_map(candles_map)
    assert "BTC/USDT:USDT" in features_map
    assert "15m" in features_map["BTC/USDT:USDT"]
    features = features_map["BTC/USDT:USDT"]["15m"]
    assert not features.empty
    assert FeatureEngineer.ensure_map_no_lookahead(candles_map, features_map)

