"""Pydantic-валидаторы конфигураций проекта."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Literal

import yaml
from pydantic import BaseModel, Field, RootModel, field_validator, model_validator

from prod_core.data import SymbolFeedSpec
from prod_core.data.feed import timeframe_to_timedelta

class RiskLimits(BaseModel):
    per_trade_r_pct_base: float = Field(gt=0, lt=5)
    risk_bonus_threshold_pct: float = Field(ge=0, le=5)
    risk_bonus_add: float = Field(ge=0, le=5)
    max_per_trade_r_pct: float = Field(gt=0, lt=5)
    max_daily_loss_pct: float = Field(gt=0, lt=10)
    kill_switch_drawdown_72h: float = Field(gt=0, lt=10)
    leverage_cap: float = Field(gt=0, le=10)
    max_portfolio_r_pct: float = Field(gt=0, lt=10)
    volatility_threshold: float = Field(gt=0, lt=1)
    volatility_risk_step: float = Field(gt=0, lt=1)
    losing_streak_lookback: int = Field(ge=1, le=10)
    min_r_pct_floor: float = Field(gt=0, lt=5)

    @field_validator("max_per_trade_r_pct")
    @classmethod
    def max_vs_base(cls, value: float, info) -> float:  # type: ignore[override]
        base = info.data.get("per_trade_r_pct_base") if info.data else None
        if base and value < base:
            raise ValueError("max_per_trade_r_pct не может быть меньше базового значения.")
        return value


class DynamicRisk(BaseModel):
    losing_streak_reduction: Dict[str, float]
    volatility_reduction: Dict[str, float]

    @field_validator("losing_streak_reduction", "volatility_reduction")
    @classmethod
    def coefficients_in_range(cls, value: Dict[str, float]) -> Dict[str, float]:
        for key, coeff in value.items():
            if not 0 < coeff <= 1:
                raise ValueError(f"Коэффициент {key} должен быть в диапазоне (0, 1].")
        return value


class GovernanceSettings(BaseModel):
    cooling_period_minutes: int = Field(ge=0, le=360)
    enable_daily_lock: bool
    enable_kill_switch: bool


class PaperGovernance(BaseModel):
    risk: RiskLimits
    dynamic_risk: DynamicRisk
    governance: GovernanceSettings


class GovernanceConfig(BaseModel):
    paper: PaperGovernance


class EnableMapConfig(RootModel[Dict[str, List[str]]]):
    """Root-only config that maps regimes to strategy lists."""

    @model_validator(mode="after")
    def ensure_lowercase(self) -> "EnableMapConfig":
        self.root = {key.lower(): strategies for key, strategies in self.root.items()}
        return self


class SymbolEntry(BaseModel):
    name: str
    type: Literal["spot", "perp"]
    timeframes: List[str] = Field(min_length=1)
    primary_timeframe: str
    backfill_bars: int = Field(ge=50, le=2000)
    min_notional: float = Field(gt=0)
    max_leverage: float = Field(gt=0)
    quote_precision: int = Field(ge=0, le=10)
    base_precision: int = Field(ge=0, le=10)
    min_liquidity_usd: float = Field(gt=0)
    max_spread_pct: float = Field(gt=0, le=5)
    poll_interval_seconds: float = Field(gt=0, le=60)

    @field_validator("primary_timeframe")
    @classmethod
    def primary_must_be_listed(cls, value: str, info) -> str:  # type: ignore[override]
        timeframes = info.data.get("timeframes") if info.data else None
        if timeframes and value not in timeframes:
            raise ValueError("primary_timeframe должен входить в список timeframes.")
        return value

    @field_validator("timeframes")
    @classmethod
    def validate_timeframes(cls, timeframes: List[str]) -> List[str]:
        seen = set()
        for tf in timeframes:
            if tf in seen:
                raise ValueError(f"Таймфрейм {tf} указан дважды.")
            seen.add(tf)
            timeframe_to_timedelta(tf)  # re-use helper из prod_core.data.feed
        return timeframes


class SymbolsConfig(BaseModel):
    symbols: List[SymbolEntry]

    @field_validator("symbols")
    @classmethod
    def ensure_unique_names(cls, entries: List[SymbolEntry]) -> List[SymbolEntry]:
        names = [entry.name for entry in entries]
        if len(names) != len(set(names)):
            raise ValueError("Список символов содержит дубликаты.")
        return entries

    def to_feed_specs(self) -> List[SymbolFeedSpec]:
        """Преобразует конфиг в dataclass для MarketDataFeed."""

        specs: List[SymbolFeedSpec] = []
        for entry in self.symbols:
            specs.append(
                SymbolFeedSpec(
                    name=entry.name,
                    type=entry.type,
                    timeframes=tuple(entry.timeframes),
                    primary_timeframe=entry.primary_timeframe,
                    backfill_bars=entry.backfill_bars,
                    min_notional=entry.min_notional,
                    max_leverage=entry.max_leverage,
                    quote_precision=entry.quote_precision,
                    base_precision=entry.base_precision,
                    min_liquidity_usd=entry.min_liquidity_usd,
                    max_spread_pct=entry.max_spread_pct,
                    poll_interval_seconds=entry.poll_interval_seconds,
                )
            )
        return specs


class ConfigLoader:
    """Загружает и валидирует YAML-конфиги."""

    def __init__(self, base_path: str | Path = "configs") -> None:
        self.base_path = Path(base_path)

    def load_governance(self) -> GovernanceConfig:
        return GovernanceConfig.model_validate(self._read_yaml("governance.yaml"))

    def load_enable_map(self) -> EnableMapConfig:
        return EnableMapConfig.model_validate(self._read_yaml("enable_map.yaml"))

    def load_symbols(self) -> SymbolsConfig:
        return SymbolsConfig.model_validate(self._read_yaml("symbols.yaml"))

    def _read_yaml(self, filename: str) -> dict:
        path = self.base_path / filename
        if not path.exists():
            raise FileNotFoundError(f"Конфиг не найден: {path}")
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return data
