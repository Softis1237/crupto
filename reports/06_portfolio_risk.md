# Portfolio & Risk Governance

## Ограничения
- `max_portfolio_r_pct = 1.5`: суммарный риск открытых и pending-позиций.
- `max_concurrent_r_pct = 1.1`: потолок риска, который может быть добавлен одним планом.
- `max_gross_exposure_pct = 300%`: совокупная абсолютная экспозиция относительно equity.
- `max_net_exposure_pct = 150%`: чистая (directional) экспозиция, учитывая long/short направления.
- `max_abs_correlation = 0.60`, `max_high_corr_positions = 2`: более двух сильно коррелирующих позиций запрещены.
- Safe-mode: при `corr_max ≥ 0.60` динамический риск-кап = `max_portfolio_r_pct × clamp(1 - (corr_max - 0.60)/(1 - 0.60), safe_mode_r_multiplier, 1.0)`. При `safe_mode_action=block` новые планы блокируются полностью.

## Корреляции
- Rolling-окно: 1 час (порядка 12 баров по 5 м / 60 баров по 1 м). `PortfolioController.update_correlation` принимает рассчитанные значения и хранит их в `correlations`.
- Частота пересчёта регулируется `correlation_refresh_seconds` (по умолчанию 1800s), чтобы не дергать биржу чрезмерно.
- `PortfolioController.safe_mode_strength` отражает максимальную абсолютную корреляцию среди активных инструментов. При превышении порога safe-mode включается, `portfolio_safe_mode`=1, а `RiskController` использует динамический cap из новой формулы.
- В режиме safe-mode важно зафиксировать причину (какие пары дали пики), при необходимости отключить менее устойчивые стратегии либо разнести активы.

## Поведение RiskManagerAgent
- Перед расчётом планов вызывается `begin_cycle`: инициализация текущего риска/экспозиции из состояния портфеля.
- Каждая стратегия запрашивает `PortfolioController.can_allocate(...)` до добавления плана.
- При утверждении плана `register_position` обновляет pending-риск и экспозиции, чтобы последующие стратегии видели уже занятую ёмкость.
- В state-требованиях необходимо передавать:
  - `portfolio_risk_pct` — текущая загрузка.
  - `gross_exposure_pct`, `net_exposure_pct` — агрегированные экспозиции (для paper пока 0, но интерфейс готов).

## Динамическое снижение риска
- Базовые параметры из `RiskEngine`: `per_trade_r_pct_base=0.8`, бонус +0.3 при `daily_pnl_pct ≥ 0.5`, верхняя граница 1.1.
- Losing streak → мультипликатор (0.9/0.8/0.7/0.6), волатильность выше `0.04` снижает риск согласно `volatility_risk_step`.
- При превышении `max_daily_loss_pct` или `kill_switch_drawdown_72h` все планы отклоняются (`guard_drawdown`).

## Проверки и мониторинг
- Метрики `pnl_cum_r`, `winrate`, `avg_win_r`, `avg_loss_r`, `max_dd_r`, `execution_reject_rate` экспортируются в Prometheus.
- Grafana dashboard содержит отдельные панели для Stage latency, Node Graph и Performance.
- При алерте `PortfolioSafeModeStuck`: выгрузить rolling-корреляции за 1 ч (см. `notebooks/` или скрипт в research pipeline), проверить `safe_mode_strength`, скорректировать enable_map/лимиты и убедиться, что feed перешёл в REST при необходимости (`--feed-timeout`).

