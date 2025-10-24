"""Контроль портфельных ограничений и корреляций."""

from __future__ import annotations

from collections import defaultdict
import logging
from dataclasses import dataclass, field
from math import isclose
from typing import Dict, Tuple
import os
import time

logger = logging.getLogger(__name__)

from prod_core.persist import (
    EquitySnapshotPayload,
    PersistDAO,
    PositionPayload,
    TradePayload,
)


@dataclass(slots=True)
class PortfolioLimits:
    """Жёсткие ограничения портфеля."""

    max_portfolio_r_pct: float = 1.5
    max_concurrent_r_pct: float = 1.1
    max_gross_exposure_pct: float = 300.0
    max_net_exposure_pct: float = 150.0
    max_abs_correlation: float = 0.6
    max_high_corr_positions: int = 2
    safe_mode_r_multiplier: float = 0.5
    correlation_window_bars: int = 288
    correlation_refresh_seconds: int = 1800
    safe_mode_action: str = "reduce"


@dataclass(slots=True)
class PositionRecord:
    """Информация об ожидаемой позиции в процентах от капитала."""

    symbol: str
    risk_pct: float
    notional_pct: float
    direction: int
    leverage: float


class PortfolioController:
    """Отвечает за лимиты по риску, экспозициям и корреляциям."""

    def __init__(
        self,
        limits: PortfolioLimits | None = None,
        dao: PersistDAO | None = None,
        base_equity: float | None = None,
    ) -> None:
        self.limits = limits or PortfolioLimits()
        self.pending: Dict[str, PositionRecord] = {}
        self.correlations: Dict[Tuple[str, str], float] = defaultdict(float)
        self._last_corr_timestamp: Dict[Tuple[str, str], int] = defaultdict(int)
        self.safe_mode = False
        self.safe_mode_strength = 0.0
        self._safe_mode_multiplier = 1.0
        self._risk_cap_pct = self.limits.max_portfolio_r_pct
        self._base_risk_pct = 0.0
        self._base_gross_exposure_pct = 0.0
        self._base_net_exposure_pct = 0.0
        self.dao = dao
        self.base_equity = base_equity or float(os.getenv("PAPER_EQUITY", "10000"))
        self.last_prices: Dict[str, float] = {}
        self.cum_pnl_r: float = 0.0
        self.cum_realized_usd: float = 0.0
        self.peak_pnl_r: float = 0.0
        self.max_dd_r: float = 0.0

    def begin_cycle(
        self,
        *,
        current_risk_pct: float,
        gross_exposure_pct: float = 0.0,
        net_exposure_pct: float = 0.0,
    ) -> None:
        """Сбрасывает временные накопители перед расчётом нового набора планов."""

        self.pending.clear()
        self._base_risk_pct = max(0.0, current_risk_pct)
        self._base_gross_exposure_pct = max(0.0, gross_exposure_pct)
        self._base_net_exposure_pct = net_exposure_pct

    def current_risk(self) -> float:
        """Возвращает суммарный риск с учётом pending-позиций."""

        pending = sum(position.risk_pct for position in self.pending.values())
        return self._base_risk_pct + pending

    def gross_exposure_pct(self) -> float:
        """Возвращает абсолютную экспозицию портфеля."""

        pending = sum(abs(position.notional_pct) for position in self.pending.values())
        return self._base_gross_exposure_pct + pending

    def net_exposure_pct(self) -> float:
        """Возвращает чистую экспозицию с учётом направления."""

        pending = sum(position.direction * position.notional_pct for position in self.pending.values())
        return self._base_net_exposure_pct + pending

    def update_correlation(self, symbol_a: str, symbol_b: str, value: float) -> None:
        """Обновляет оценку корреляции между активами."""

        key = self._correlation_key(symbol_a, symbol_b)
        now = int(time.time())
        last = self._last_corr_timestamp.get(key, 0)
        previous = self.correlations.get(key)
        threshold = self.limits.max_abs_correlation
        crosses_threshold = False
        if previous is not None:
            previously_high = abs(previous) >= threshold
            currently_high = abs(value) >= threshold
            crosses_threshold = previously_high != currently_high
        if (
            previous is not None
            and (now - last) < self.limits.correlation_refresh_seconds
            and not crosses_threshold
        ):
            return
        self.correlations[key] = value
        self._last_corr_timestamp[key] = now
        self._recompute_safe_mode()

    def can_allocate(
        self,
        symbol: str,
        additional_r_pct: float,
        notional_pct: float,
        direction: int,
    ) -> bool:
        """Проверяет возможность выделения риска и экспозиции."""

        if additional_r_pct <= 0:
            return False
        if additional_r_pct > self.limits.max_concurrent_r_pct:
            return False

        if self.current_risk() + additional_r_pct > self._risk_cap_pct:
            return False

        if self.gross_exposure_pct() + abs(notional_pct) > self.limits.max_gross_exposure_pct:
            return False

        projected_net = self.net_exposure_pct() + direction * notional_pct
        if abs(projected_net) > self.limits.max_net_exposure_pct:
            return False

        if self._count_highly_correlated(symbol) >= self.limits.max_high_corr_positions:
            return False

        if self.safe_mode and self.limits.safe_mode_action.lower() == "block":
            logger.info(
                "Safe-mode blocks allocation for %s (run=%s)",
                symbol,
                self.dao.run_id if self.dao else "n/a",
            )
            return False
        return True

    def register_position(
        self,
        symbol: str,
        risk_pct: float,
        notional_pct: float,
        direction: int,
        leverage: float,
    ) -> None:
        """Фиксирует pending-позицию внутри текущего цикла."""

        self.pending[symbol] = PositionRecord(
            symbol=symbol,
            risk_pct=risk_pct,
            notional_pct=notional_pct,
            direction=direction,
            leverage=leverage,
        )
        self._recompute_safe_mode()

    def _count_highly_correlated(self, symbol: str) -> int:
        """Возвращает количество позиций, высоко коррелирующих с указанной."""

        count = 0
        for existing in self.pending:
            if existing == symbol:
                continue
            corr = abs(self.correlations.get(self._correlation_key(symbol, existing), 0.0))
            if corr >= self.limits.max_abs_correlation:
                count += 1
        return count

    def _recompute_safe_mode(self) -> None:
        """Обновляет safe-mode, динамический риск-кап и логирует переходы."""

        active_symbols = set(self.pending.keys())
        if self.dao:
            try:
                for position in self.dao.fetch_positions():
                    qty = float(position.get("qty", 0.0))
                    if abs(qty) > 0:
                        active_symbols.add(str(position["symbol"]))
            except Exception:  # pragma: no cover - защитный контур
                logger.exception("Не удалось получить позиции для safe-mode пересчёта.")

        threshold = self.limits.max_abs_correlation
        if len(active_symbols) < 2:
            if self.safe_mode:
                logger.info(
                    "Safe-mode exit: менее двух активных инструментов (run=%s)",
                    self.dao.run_id if self.dao else "n/a",
                )
            self.safe_mode = False
            self.safe_mode_strength = 0.0
            self._safe_mode_multiplier = 1.0
            self._risk_cap_pct = self.limits.max_portfolio_r_pct
            return

        symbols = sorted(active_symbols)
        max_corr = 0.0
        for i, left in enumerate(symbols):
            for right in symbols[i + 1 :]:
                key = self._correlation_key(left, right)
                corr = abs(self.correlations.get(key, 0.0))
                max_corr = max(max_corr, corr)

        prev_state = self.safe_mode
        prev_multiplier = self._safe_mode_multiplier
        self.safe_mode_strength = max_corr

        if max_corr < threshold:
            if prev_state:
                logger.info(
                    "Safe-mode exit: corr_max=%.3f < %.2f (run=%s)",
                    max_corr,
                    threshold,
                    self.dao.run_id if self.dao else "n/a",
                )
            self.safe_mode = False
            self._safe_mode_multiplier = 1.0
            self._risk_cap_pct = self.limits.max_portfolio_r_pct
            return

        if not prev_state:
            logger.warning(
                "Safe-mode entry: corr_max=%.3f ≥ %.2f (run=%s)",
                max_corr,
                threshold,
                self.dao.run_id if self.dao else "n/a",
            )

        self.safe_mode = True
        denom = max(1e-6, 1.0 - threshold)
        raw_multiplier = 1.0 - max(0.0, max_corr - threshold) / denom
        multiplier = max(self.limits.safe_mode_r_multiplier, min(1.0, raw_multiplier))
        self._safe_mode_multiplier = multiplier
        self._risk_cap_pct = self.limits.max_portfolio_r_pct * multiplier

        if prev_state and abs(prev_multiplier - multiplier) > 1e-3:
            logger.info(
                "Safe-mode adjust: corr_max=%.3f multiplier=%.2f cap=%.2f%% (run=%s)",
                max_corr,
                multiplier,
                self._risk_cap_pct,
                self.dao.run_id if self.dao else "n/a",
            )
    @staticmethod
    def _correlation_key(symbol_a: str, symbol_b: str) -> Tuple[str, str]:
        if symbol_a <= symbol_b:
            return (symbol_a, symbol_b)
        return (symbol_b, symbol_a)

    def apply_fill(
        self,
        *,
        order_id: int,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        fee: float = 0.0,
        timestamp: int | None = None,
    ) -> None:
        """Отражает исполнение сделки в персист-слое."""

        if not self.dao:
            return

        ts = timestamp or int(time.time())
        qty_change = qty if side.lower() == "buy" else -qty
        self.last_prices[symbol] = price

        position = self.dao.fetch_position(symbol)
        existing_qty = float(position.get("qty", 0.0)) if position else 0.0
        avg_price = float(position.get("avg_price", price)) if position else price
        realized_pnl_r_symbol = float(position.get("realized_pnl_r", 0.0)) if position else 0.0

        new_qty = existing_qty + qty_change
        realized_usd = 0.0
        pnl_r_trade = 0.0

        # Определяем закрываемый объём
        if existing_qty != 0 and existing_qty * qty_change < 0:
            closing_qty = min(abs(existing_qty), abs(qty_change))
            if existing_qty > 0:
                realized_usd = (price - avg_price) * closing_qty
            else:
                realized_usd = (avg_price - price) * closing_qty

            risk_unit_usd = max(self.base_equity * 0.008, 1e-6)
            pnl_r_trade = realized_usd / risk_unit_usd
            realized_pnl_r_symbol += pnl_r_trade

            # Обновляем количество после закрытия части
            if abs(qty_change) > abs(existing_qty):
                # Реверс позиции: сначала закрываем, остаток — новая позиция
                residual = qty_change + existing_qty
                new_qty = residual
                avg_price = price
            else:
                new_qty = existing_qty + qty_change
        else:
            # Добавление к позиции или открытие новой
            combined_qty = existing_qty + qty_change
            if combined_qty != 0:
                avg_price = ((existing_qty * avg_price) + (qty_change * price)) / combined_qty
            new_qty = combined_qty

        exposure_usd = new_qty * price
        unrealized_pnl_r = 0.0  # без mark-to-market

        if isclose(new_qty, 0.0, abs_tol=1e-8):
            self.dao.clear_position(symbol, run_id=self.dao.run_id if self.dao else None)
        else:
            self.dao.upsert_position(
                PositionPayload(
                    symbol=symbol,
                    ts=ts,
                    qty=new_qty,
                    avg_price=avg_price,
                    unrealized_pnl_r=unrealized_pnl_r,
                    realized_pnl_r=realized_pnl_r_symbol,
                    exposure_usd=exposure_usd,
                    meta={"last_price": price},
                    run_id=self.dao.run_id if self.dao else None,
                )
            )

        if pnl_r_trade != 0.0 or fee != 0.0:
            self.cum_pnl_r += pnl_r_trade
            self.cum_realized_usd += realized_usd - fee
            self.peak_pnl_r = max(self.peak_pnl_r, self.cum_pnl_r)
            drawdown = self.peak_pnl_r - self.cum_pnl_r
            self.max_dd_r = max(self.max_dd_r, drawdown)

        trade_payload = TradePayload(
            order_id=order_id,
            ts=ts,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            fee=fee,
            pnl_r=pnl_r_trade,
            meta={"qty_change": qty_change},
            run_id=self.dao.run_id if self.dao else None,
        )
        self.dao.insert_trade(trade_payload)

        equity_usd = self.base_equity + self.cum_realized_usd
        positions = self.dao.fetch_positions()
        gross_usd = 0.0
        net_usd = 0.0
        for pos in positions:
            mark_price = self.last_prices.get(pos["symbol"], pos.get("avg_price", price))
            exposure = float(pos["qty"]) * mark_price
            gross_usd += abs(exposure)
            net_usd += exposure
        gross_pct = (gross_usd / equity_usd * 100) if equity_usd else 0.0
        net_pct = (net_usd / equity_usd * 100) if equity_usd else 0.0

        self.dao.insert_equity_snapshot(
            EquitySnapshotPayload(
                ts=ts,
                equity_usd=equity_usd,
                pnl_r_cum=self.cum_pnl_r,
                max_dd_r=self.max_dd_r,
                exposure_gross=gross_pct,
                exposure_net=net_pct,
                run_id=self.dao.run_id if self.dao else None,
            )
        )
        self._recompute_safe_mode()
