# Portfolio & Risk Governance

## Ограничения
- `max_portfolio_r_pct = 1.5`: суммарный риск открытых и pending-позиций.
- `max_concurrent_r_pct = 1.1`: потолок риска, который может быть добавлен одним планом.
- `max_gross_exposure_pct = 300%`: совокупная абсолютная экспозиция относительно equity.
- `max_net_exposure_pct = 150%`: чистая (directional) экспозиция, учитывая long/short направления.
- `max_abs_correlation = 0.7`, `max_high_corr_positions = 2`: более двух сильно коррелирующих позиций запрещены.
- Safe-mode: если вся корзина pending-позиций высоко коррелирует, разрешается не более `safe_mode_r_multiplier=0.5` от портфельного риска.

## Корреляции
- `PortfolioController.update_correlation` обновляет оценки парных корреляций (rolling окно 288 баров, пересчёт каждые 30 минут — значение из `reports/07`).
- Частота пересчёта регулируется `correlation_refresh_seconds` (по умолчанию 1800s), чтобы не дергать биржу чрезмерно.
- `PortfolioController` автоматически активирует safe-mode, когда все пары превышают порог и экспортирует метрику `portfolio_safe_mode`.
- В режиме safe-mode новые планы отклоняются либо существенно урезаются (см. multiplier выше).

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
- При активации safe-mode необходимо зафиксировать событие в RUNBOOK и уменьшить торговую активность (приоритет — митигация корреляций).
