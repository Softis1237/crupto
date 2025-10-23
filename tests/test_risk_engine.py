import time
from datetime import datetime, timezone

from prod_core.persist import EquitySnapshotPayload, PersistDAO

from prod_core.risk.engine import RiskEngine, RiskSettings, RiskState
from prod_core.strategies.base import StrategySignal


def make_state(**overrides) -> RiskState:
    base = {
        "equity": 10000.0,
        "daily_pnl_pct": 0.0,
        "trailing_drawdown_72h_pct": -1.0,
        "losing_streak": 0,
        "realized_volatility": 0.02,
        "portfolio_risk_pct": 0.5,
    }
    base.update(overrides)
    return RiskState(**base)


def test_risk_bonus_applied() -> None:
    engine = RiskEngine()
    state = make_state(daily_pnl_pct=0.6)
    risk = engine.risk_budget_pct(state)
    assert risk <= engine.settings.max_per_trade_r_pct
    assert risk >= engine.settings.per_trade_r_pct_base


def test_dynamic_reduction_on_losing_streak() -> None:
    engine = RiskEngine()
    state = make_state(losing_streak=4)
    reduced = engine.risk_budget_pct(state)
    base = engine.settings.per_trade_r_pct_base
    assert reduced < base


def test_size_position_respects_leverage() -> None:
    settings = RiskSettings(leverage_cap=2.0)
    engine = RiskEngine(settings=settings)
    state = make_state()
    signal = StrategySignal(timestamp=datetime.now(tz=timezone.utc), side="long", confidence=1.0)
    signal.stop_loss = 9900
    size = engine.size_position(signal, entry_price=10000, state=state, atr=100)
    leverage = size * 10000 / state.equity
    assert leverage <= settings.leverage_cap + 1e-6


def test_size_position_uses_persist_equity(tmp_path) -> None:
    run_id = "risk_engine_test"
    dao = PersistDAO(tmp_path / "risk_engine.db", run_id=run_id)
    dao.initialize()
    dao.insert_equity_snapshot(
        EquitySnapshotPayload(
            ts=int(time.time()),
            equity_usd=8000.0,
            pnl_r_cum=0.0,
            max_dd_r=0.0,
            exposure_gross=0.0,
            exposure_net=0.0,
            run_id=run_id,
        )
    )
    engine = RiskEngine(dao=dao)
    state = make_state(equity=0.0)
    signal = StrategySignal(timestamp=datetime.now(tz=timezone.utc), side="long", confidence=1.0)
    signal.stop_loss = 950.0
    size = engine.size_position(signal, entry_price=1000.0, state=state, atr=20.0)
    assert size > 0.0
