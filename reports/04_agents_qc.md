# QC метрики агентов

**MarketRegimeAgent**
- accuracy ≥ 0.8 на размеченном датасете режимов.
- F1 для метки panic ≥ 0.7 (несбалансированный класс отдельной выборкой).
- Ложные переключения ≤ 1 в час (гистерезис на EMA, волатильности).

**StrategySelectionAgent**
- Отбраковка стратегий по скорингу ≤ 40% в трендовых режимах, ≥ 60% в боковиках.
- Cooldown: повторный запуск стратегии не ранее чем через `min_hold_bars`/2 (мониторинг через метрику `strategy_cooldown_state`).
- Hysteresis: min_bars_hold соблюден в 95% случаев (pytest mock pipeline).

**RiskManagerAgent**
- План без stop_loss → тест проваливается.
- Drawdown guard должен блокировать сделки при daily_pnl ≤ -max_daily_loss_pct (unit test).
- Согласование размера позиции с RiskEngine: расхождение ≤ 1% (property test).

**ExecutionAgent**
- Ликвидность: заявки > `max_contracts` отклоняются (метрика `execution_rejected_liquidity`).
- Слиппедж: ошибка прогноза ≤ 20% (сравнение с фактическим при paper-прогоне).

**ResearchAgent**
- Генератор кандидатов даёт стабильный hash id (детерминизм).
- Walk-forward + Monte-Carlo должны проходить champion thresholds (PF, Sharpe, DD).
