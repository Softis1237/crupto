from datetime import datetime, timezone

from prod_core.risk.governor import DailyGovernor, GovernanceLimits


def test_governor_locks_on_daily_loss() -> None:
    governor = DailyGovernor(GovernanceLimits(max_daily_loss_pct=1.0))
    governor.register_trade_result(-1.2)
    assert not governor.should_trade()


def test_governor_kill_switch() -> None:
    governor = DailyGovernor(GovernanceLimits(kill_switch_drawdown_72h=2.0))
    governor.update_drawdown(-2.5)
    assert not governor.should_trade()


def test_governor_resets_day() -> None:
    governor = DailyGovernor()
    governor.register_trade_result(-2.0)
    governor.reset_day(now=datetime.now(tz=timezone.utc))
    assert governor.should_trade()
