"""Губернатор риска: контроль дневных лимитов и kill-switch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(slots=True)
class GovernanceLimits:
    """Жёсткие рамки risk governance."""

    max_daily_loss_pct: float = 1.8
    kill_switch_drawdown_72h: float = 3.5
    cooling_period_minutes: int = 60


@dataclass(slots=True)
class GovernorState:
    """Состояние риск-губернатора."""

    day_started_at: datetime
    day_pnl_pct: float = 0.0
    drawdown_72h_pct: float = 0.0
    locked: bool = False
    kill_switch_engaged: bool = False
    last_unlock_check: datetime | None = None


class DailyGovernor:
    """Отвечает за daily-lock и kill-switch."""

    def __init__(self, limits: GovernanceLimits | None = None) -> None:
        self.limits = limits or GovernanceLimits()
        now = datetime.now(tz=timezone.utc)
        self.state = GovernorState(day_started_at=now)

    def register_trade_result(self, pnl_pct: float) -> None:
        """Обновляет дневной результат и пересчитывает состояние блокировок."""

        self.state.day_pnl_pct += pnl_pct
        self._update_lock_state()

    def update_drawdown(self, drawdown_72h_pct: float) -> None:
        """Сохраняет текущее значение 72h дроудауна."""

        self.state.drawdown_72h_pct = drawdown_72h_pct
        self._update_lock_state()

    def should_trade(self, now: datetime | None = None) -> bool:
        """Возвращает True, если разрешено выставлять новые заявки."""

        if now is None:
            now = datetime.now(tz=timezone.utc)
        state = self.state
        if state.kill_switch_engaged:
            return False
        if state.locked:
            if state.last_unlock_check and (now - state.last_unlock_check).total_seconds() < self.limits.cooling_period_minutes * 60:
                return False
            state.last_unlock_check = now
            return False
        return True

    def reset_day(self, now: datetime | None = None) -> None:
        """Сбрасывает дневной счётчик (по cron в начале UTC-дня)."""

        now = now or datetime.now(tz=timezone.utc)
        self.state = GovernorState(day_started_at=now, drawdown_72h_pct=self.state.drawdown_72h_pct)

    def _update_lock_state(self) -> None:
        """Пересчитывает блокировки по лимитам."""

        limits = self.limits
        state = self.state
        if state.drawdown_72h_pct <= -limits.kill_switch_drawdown_72h:
            state.kill_switch_engaged = True
            state.locked = True
            return
        if state.day_pnl_pct <= -limits.max_daily_loss_pct:
            state.locked = True
        else:
            state.locked = False
