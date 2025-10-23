import pytest

from prod_core.exec.portfolio import PortfolioController, PortfolioLimits


def test_portfolio_respects_risk_cap() -> None:
    limits = PortfolioLimits(max_portfolio_r_pct=1.5, max_concurrent_r_pct=1.1)
    controller = PortfolioController(limits=limits)
    controller.begin_cycle(current_risk_pct=1.0)
    assert controller.can_allocate("BTC/USDT", additional_r_pct=0.4, notional_pct=50.0, direction=1)
    controller.register_position("BTC/USDT", risk_pct=0.4, notional_pct=50.0, direction=1, leverage=1.0)
    assert not controller.can_allocate("ETH/USDT", additional_r_pct=0.3, notional_pct=40.0, direction=1)


def test_safe_mode_restricts_allocations() -> None:
    limits = PortfolioLimits(
        max_portfolio_r_pct=1.5,
        max_abs_correlation=0.6,
        max_high_corr_positions=1,
        safe_mode_r_multiplier=0.5,
    )
    controller = PortfolioController(limits=limits)
    controller.begin_cycle(current_risk_pct=0.5)
    assert controller.can_allocate("BTC/USDT", 0.4, 30.0, 1)
    controller.register_position("BTC/USDT", risk_pct=0.4, notional_pct=30.0, direction=1, leverage=1.0)
    controller.update_correlation("BTC/USDT", "ETH/USDT", 0.9)
    expected_cap = limits.max_portfolio_r_pct * controller._safe_mode_multiplier
    assert controller._risk_cap_pct == pytest.approx(expected_cap)
    assert controller._safe_mode_multiplier >= limits.safe_mode_r_multiplier
    assert not controller.can_allocate("ETH/USDT", 0.4, 30.0, 1)
