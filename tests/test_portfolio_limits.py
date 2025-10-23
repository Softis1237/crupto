from prod_core.exec.portfolio import PortfolioController, PortfolioLimits


def test_gross_and_net_limits() -> None:
    limits = PortfolioLimits(max_portfolio_r_pct=1.5, max_gross_exposure_pct=120.0, max_net_exposure_pct=80.0)
    controller = PortfolioController(limits=limits)
    controller.begin_cycle(current_risk_pct=0.5, gross_exposure_pct=40.0, net_exposure_pct=10.0)

    assert controller.can_allocate("BTC", additional_r_pct=0.5, notional_pct=30.0, direction=1)
    controller.register_position("BTC", risk_pct=0.5, notional_pct=30.0, direction=1, leverage=1.0)

    # превышение gross экспозиции
    assert not controller.can_allocate("ETH", additional_r_pct=0.6, notional_pct=80.0, direction=1)

    # превышение net экспозиции в обратную сторону не допускается
    assert not controller.can_allocate("ETH", additional_r_pct=0.3, notional_pct=50.0, direction=1)


def test_safe_mode_triggers_on_high_correlation() -> None:
    controller = PortfolioController(limits=PortfolioLimits(correlation_refresh_seconds=0))
    controller.begin_cycle(current_risk_pct=0.0)
    controller.register_position("BTC", risk_pct=0.6, notional_pct=30.0, direction=1, leverage=1.0)
    controller.update_correlation("BTC", "ETH", 0.85)
    controller.register_position("ETH", risk_pct=0.6, notional_pct=35.0, direction=1, leverage=1.0)

    assert controller.safe_mode is True
    safe_cap = controller.limits.max_portfolio_r_pct * controller.limits.safe_mode_r_multiplier
    assert safe_cap == controller.limits.max_portfolio_r_pct * controller.limits.safe_mode_r_multiplier


def test_safe_mode_blocks_when_action_block() -> None:
    limits = PortfolioLimits(safe_mode_action="block")
    controller = PortfolioController(limits=limits)
    controller.begin_cycle(current_risk_pct=0.0)
    controller.register_position("BTC", risk_pct=0.5, notional_pct=25.0, direction=1, leverage=1.0)
    controller.update_correlation("BTC", "ETH", limits.max_abs_correlation + 0.1)
    controller.register_position("ETH", risk_pct=0.5, notional_pct=25.0, direction=1, leverage=1.0)

    assert controller.safe_mode is True
    assert not controller.can_allocate("ADA", additional_r_pct=0.1, notional_pct=5.0, direction=1)


def test_safe_mode_exits_when_correlation_drops() -> None:
    controller = PortfolioController(limits=PortfolioLimits(correlation_refresh_seconds=0))
    controller.begin_cycle(current_risk_pct=0.0)
    controller.register_position("BTC", risk_pct=0.4, notional_pct=20.0, direction=1, leverage=1.0)
    controller.update_correlation("BTC", "ETH", 0.9)
    controller.register_position("ETH", risk_pct=0.4, notional_pct=20.0, direction=1, leverage=1.0)
    assert controller.safe_mode is True

    controller.update_correlation("BTC", "ETH", 0.2)
    assert controller.safe_mode is False
    assert controller.can_allocate("ADA", additional_r_pct=0.1, notional_pct=5.0, direction=1)

