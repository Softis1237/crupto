# Валидация конфигов

## Governance (`configs/governance.yaml`)
- Pydantic: `GovernanceConfig` → `PaperGovernance` → `RiskLimits`, `DynamicRisk`, `GovernanceSettings`.
- Проверки:
  - все значения риска > 0; `max_per_trade_r_pct ≥ per_trade_r_pct_base`.
  - коэффициенты снижения streak/volatility ∈ (0,1].
  - `cooling_period_minutes ≤ 360`.
- Ошибки → `ValueError` при `ConfigLoader.load_governance()`.

## Enable map (`configs/enable_map.yaml`)
- Pydantic: `EnableMapConfig` (`dict[str, list[str]]`).
- Ключи приводятся к lowercase, пустые списки запрещены.

## Symbols (`configs/symbols.yaml`)
- Pydantic: `SymbolsConfig` (`List[SymbolEntry]`).
- Поля SymbolEntry:
  - `type ∈ {spot, perp}`.
  - `timeframes` — непустой список, значения валидируются через `timeframe_to_timedelta`.
  - `primary_timeframe` обязан присутствовать в `timeframes`.
  - `backfill_bars ≥ 2000`.
  - `min_notional > 0`, `max_leverage > 0`, `precision ∈ [0,10]`.
  - `min_liquidity_usd > 0`, `max_spread_pct > 0`, `poll_interval_seconds ∈ (0,60]`.
- Уникальность `name` проверяется на уровне `SymbolsConfig`.
- `to_feed_specs()` конвертирует записи в `SymbolFeedSpec` для `MarketDataFeed`.

## Использование
- Runner загружает все конфиги через `ConfigLoader` перед запуском feed.
- Любая ошибка валидации → остановка процесса и запись события в `reports/00_repo_audit.md` / telemetry.
