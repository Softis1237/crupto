"""Точка входа paper-режима с реальным CCXT-фидом."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
from pathlib import Path
import time
from typing import Dict, Tuple

import pandas as pd
import logging

from brain_orchestrator.brain import BrainOrchestrator
from brain_orchestrator.tools import ToolRegistry
from dashboards.exporter import serve_prometheus
from prod_core.configs.loader import ConfigLoader
from research_lab.backtests.vectorbt_runner import load_shadow_strategies
from prod_core.data import FeedHealthStatus, MarketDataFeed, MockMarketDataFeed
from prod_core.exec.portfolio import PortfolioController
from prod_core.monitor import TelemetryExporter, configure_logging
from prod_core.persist import EquitySnapshotPayload, PersistDAO
from prod_core.persist.shadow_logger import ShadowLogger
from prod_core.risk import RiskEngine
from prod_core.strategies import (
    Breakout4HStrategy,
    FundingReversionStrategy,
    RangeReversion5MStrategy,
    TradingStrategy,
    VolatilityExpansion15MStrategy,
)

logger = logging.getLogger(__name__)


def _load_dotenv_from_root() -> None:
    """Load .env and .env.local from the repository root if present.

    Existing environment variables are not overridden so values exported in
    the shell still take precedence.
    """
    try:
        root = Path(__file__).resolve().parents[1]
    except Exception:
        return
    for name in (".env", ".env.local"):
        path = root / name
        if not path.exists():
            continue
        logger.info("Loading environment variables from %s", str(path))
        try:
            with path.open("r", encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    # remove surrounding quotes if present
                    if (val.startswith("\"") and val.endswith("\"")) or (
                        val.startswith("'") and val.endswith("'")
                    ):
                        val = val[1:-1]
                    if key and os.getenv(key) is None:
                        os.environ[key] = val
        except Exception:
            logger.exception("Failed to load env file: %s", str(path))


def build_strategies() -> list[TradingStrategy]:
    """Возвращает набор зарегистрированных стратегий."""

    return [
        Breakout4HStrategy(),
        VolatilityExpansion15MStrategy(),
        RangeReversion5MStrategy(),
        FundingReversionStrategy(),
    ]


def ensure_paper_mode() -> str:
    """Гарантирует, что режим paper включён."""

    mode = os.getenv("MODE", "paper").lower()
    if mode != "paper":
        raise RuntimeError("MODE=live запрещён до прохождения Acceptance.")
    return mode


def connect_registry(
    telemetry: TelemetryExporter,
    *,
    dao: PersistDAO | None = None,
    portfolio: PortfolioController | None = None,
    exchange_id: str | None = None,
) -> ToolRegistry:
    """Создаёт ToolRegistry и пробрасывает TelemetryExporter."""

    registry = ToolRegistry()
    try:
        exporter_tool = registry.resolve("export_metrics")
        if hasattr(exporter_tool, "telemetry"):
            exporter_tool.telemetry = telemetry  # type: ignore[attr-defined]
    except KeyError:
        pass
    if dao and portfolio:
        try:
            placer_tool = registry.resolve("place_order")
            if hasattr(placer_tool, "configure_persistence"):
                placer_tool.configure_persistence(
                    dao=dao,
                    portfolio=portfolio,
                    exchange=exchange_id,
                )  # type: ignore[attr-defined]
        except KeyError:
            pass
    return registry


def _aggregate_health(statuses: Dict[str, Dict[str, FeedHealthStatus]]) -> int:
    """Возвращает 1, если все источники в статусе OK, иначе 0."""

    for per_symbol in statuses.values():
        for status in per_symbol.values():
            if status != FeedHealthStatus.OK:
                return 0
    return 1


def _build_state(dao: PersistDAO) -> Dict[str, float]:
    """Формирует состояние риска на основе персист-хранилища."""

    default_equity = float(os.getenv("PAPER_EQUITY", "10000"))
    snapshot = dao.fetch_equity_last()
    positions = dao.fetch_positions()

    if snapshot is None:
        dao.insert_equity_snapshot(
            EquitySnapshotPayload(
                ts=int(time.time()),
                equity_usd=default_equity,
                pnl_r_cum=0.0,
                max_dd_r=0.0,
                exposure_gross=0.0,
                exposure_net=0.0,
                run_id=dao.run_id,
            )
        )
        snapshot = dao.fetch_equity_last()

    equity = float(snapshot["equity_usd"]) if snapshot else default_equity
    exposure_gross = float(snapshot["exposure_gross"]) if snapshot else 0.0
    exposure_net = float(snapshot["exposure_net"]) if snapshot else 0.0
    portfolio_risk_pct = 0.0
    if equity > 0:
        exposure_sum = sum(abs(pos.get("exposure_usd", 0.0)) for pos in positions)
        portfolio_risk_pct = min(1.5, (exposure_sum / equity) * 100)

    return {
        "equity": equity,
        "daily_pnl_pct": 0.0,
        "drawdown_72h_pct": -float(snapshot["max_dd_r"]) if snapshot else -0.5,
        "losing_streak": 0,
        "realized_volatility": 0.02,
        "portfolio_risk_pct": portfolio_risk_pct,
        "gross_exposure_pct": exposure_gross,
        "net_exposure_pct": exposure_net,
    }


def _env_flag(name: str) -> bool:
    """Возвращает True, если переменная окружения содержит правду."""

    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_seconds(cli_value: float | None) -> float | None:
    if cli_value and cli_value > 0:
        return cli_value
    env_value = os.getenv("RUN_MAX_SECONDS")
    if env_value:
        try:
            parsed = float(env_value)
            if parsed > 0:
                return parsed
        except ValueError:
            logger.warning("Игнорируем некорректное значение RUN_MAX_SECONDS=%s", env_value)
    return None


def _resolve_cycles(cli_value: int | None) -> int | None:
    if cli_value and cli_value > 0:
        return cli_value
    env_value = os.getenv("RUN_MAX_CYCLES")
    if env_value:
        try:
            parsed = int(env_value)
            if parsed > 0:
                return parsed
        except ValueError:
            logger.warning("Игнорируем некорректное значение RUN_MAX_CYCLES=%s", env_value)
    return None


async def _run_paper_loop(
    *,
    max_seconds: float | None = None,
    max_cycles: int | None = None,
    skip_feed_check: bool = False,
    use_mock_feed: bool = False,
    feed_timeout: float | None = None,
) -> None:
    mode = ensure_paper_mode()
    if use_mock_feed and mode != "paper":
        raise RuntimeError("--use-mock-feed разрешён только в MODE=paper.")
    configure_logging()

    run_id = os.getenv("RUN_ID")
    if not run_id:
        run_id = time.strftime("paper_%Y%m%d_%H%M%S")
        os.environ["RUN_ID"] = run_id
    logger.info("Starting paper run run_id=%s", run_id)

    challenger_config = os.getenv('CHALLENGER_CONFIG')
    challengers: list[TradingStrategy] = []
    shadow_logger: ShadowLogger | None = None
    if challenger_config:
        try:
            challengers = load_shadow_strategies(Path(challenger_config))
            logger.info('Loaded %d challenger strategies from %s', len(challengers), challenger_config)
        except Exception as exc:
            logger.exception('Unable to load challengers: %s', exc)
            challengers = []
    if challengers:
        shadow_dir = Path(f'reports/run_{run_id}/shadow')
        shadow_logger = ShadowLogger(shadow_dir, run_id)
    loader = ConfigLoader()
    symbols_cfg = loader.load_symbols()
    specs = symbols_cfg.to_feed_specs()

    dao = PersistDAO(os.getenv("PERSIST_DB_PATH", "storage/crupto.db"), run_id=run_id)
    dao.initialize()

    telemetry = TelemetryExporter(csv_path="reports/telemetry_events.csv")
    prometheus_port = int(os.getenv("PROMETHEUS_PORT", "9108"))
    serve_prometheus(telemetry, prometheus_port)
    logger.info("Prometheus exporter слушает порт %s", prometheus_port)
    exchange_id = os.getenv("EXCHANGE", "binanceusdm")
    portfolio_controller = PortfolioController(dao=dao)
    registry = connect_registry(
        telemetry,
        dao=dao,
        portfolio=portfolio_controller,
        exchange_id=exchange_id,
    )
    strategies = build_strategies()
    risk_engine = RiskEngine(dao=dao)
    orchestrator = BrainOrchestrator(
        registry=registry,
        telemetry=telemetry,
        strategies=strategies,
        risk_engine=risk_engine,
        dao=dao,
        portfolio=portfolio_controller,
        challengers=challengers,
        shadow_logger=shadow_logger,
    )

    feed: MarketDataFeed | MockMarketDataFeed
    if use_mock_feed:
        logger.warning("Активирован mock-фид: цикл работает на синтетических данных.")
        feed = MockMarketDataFeed(symbols=specs)
    else:
        feed = MarketDataFeed(
            exchange_id=exchange_id,
            symbols=specs,
            use_websocket=os.getenv("ENABLE_WS", "1").lower() == "1",
        )

    stop_event = asyncio.Event()

    def _graceful_shutdown() -> None:
        logger.info("Получен сигнал завершения, останавливаемся...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, sig_name):
            try:
                loop.add_signal_handler(getattr(signal, sig_name), _graceful_shutdown)
            except NotImplementedError:
                logger.debug("Signal handlers are not supported on this platform for %s.", sig_name)

    last_processed: Dict[Tuple[str, str], pd.Timestamp] = {}
    min_required_bars = min(spec.backfill_bars for spec in specs)
    base_sleep = min(spec.poll_interval_seconds for spec in specs)
    sleep_interval = max(1.0, base_sleep)
    if use_mock_feed:
        sleep_interval = min(sleep_interval, 0.5)

    async with feed:
        effective_skip_check = skip_feed_check
        symbol_timeframes = [(spec.name, tf) for spec in specs for tf in spec.timeframes]
        if not effective_skip_check:
            timeout_value = feed_timeout if feed_timeout and feed_timeout > 0 else None
            if timeout_value is None:
                await asyncio.gather(*(feed.wait_ready(symbol, tf) for symbol, tf in symbol_timeframes))
                logger.info(
                    "Фид инициализирован: %s | таймфреймы %s | exchange=%s",
                    ", ".join(spec.name for spec in specs),
                    ", ".join(sorted({tf for spec in specs for tf in spec.timeframes})),
                    exchange_id,
                )
            else:
                readiness = await asyncio.gather(
                    *(feed.wait_ready(symbol, tf, timeout=timeout_value) for symbol, tf in symbol_timeframes)
                )
                not_ready = [f"{symbol}/{tf}" for (symbol, tf), ok in zip(symbol_timeframes, readiness) if not ok]
                if not_ready:
                    logger.warning(
                        "Таймаут %.1f с при ожидании WebSocket: %s. Переключаемся на REST-поллинг.",
                        timeout_value,
                        ", ".join(not_ready),
                    )
                    if hasattr(feed, "force_rest_mode"):
                        feed.force_rest_mode()  # type: ignore[attr-defined]
                    effective_skip_check = True
                else:
                    logger.info(
                        "Фид инициализирован: %s | таймфреймы %s | exchange=%s",
                        ", ".join(spec.name for spec in specs),
                        ", ".join(sorted({tf for spec in specs for tf in spec.timeframes})),
                        exchange_id,
                    )
        if effective_skip_check:
            logger.warning("Пропускаем feed.wait_ready(): используем REST-backfill/мок-данные.")
        start_ts = time.time()
        cycles = 0
        while not stop_event.is_set():
            if max_seconds and max_seconds > 0 and (time.time() - start_ts) >= max_seconds:
                logger.info("Достигнут лимит времени %.1f с, завершаемся.", max_seconds)
                break
            if max_cycles and max_cycles > 0 and cycles >= max_cycles:
                logger.info("Достигнут лимит по числу циклов %d, завершаемся.", max_cycles)
                break
            snapshot = feed.snapshot(min_bars=min_required_bars)
            telemetry.record_feed_health(_aggregate_health(feed.status()))

            for spec in specs:
                timeframe = spec.primary_timeframe
                candles = snapshot.get(spec.name, {}).get(timeframe)
                if candles is None or candles.empty:
                    continue
                latest_ts = candles.index[-1]
                key = (spec.name, timeframe)
                if key in last_processed and last_processed[key] >= latest_ts:
                    continue
                orchestrator.run_cycle(
                    candles=candles,
                    state=_build_state(dao),
                    mode=mode,
                    symbol=spec.name,
                    timeframe=timeframe,
                )
                last_processed[key] = latest_ts

            cycles += 1
            await asyncio.sleep(sleep_interval)

    logger.info("Paper-loop остановлен.")


def main() -> None:
    """Основная точка входа CLI."""
    # Try to load .env/.env.local from repo root so users don't need to export
    # credentials every time in an interactive shell. Existing env vars keep
    # precedence.
    _load_dotenv_from_root()

    parser = argparse.ArgumentParser(description="Paper-runner crupto.")
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="ограничение по времени выполнения (секунды)",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="ограничение по количеству циклов обработки",
    )
    parser.add_argument(
        "--skip-feed-check",
        action="store_true",
        help="пропускает ожидание готовности фида (только для отладки)",
    )
    parser.add_argument(
        "--use-mock-feed",
        action="store_true",
        help="подменяет CCXT-фид синтетическим генератором (MODE=paper)",
    )
    parser.add_argument(
        "--mode",
        choices=("paper", "live"),
        help="режим запуска (альтернатива переменной окружения MODE)",
    )
    parser.add_argument(
        "--feed-timeout",
        type=float,
        default=None,
        help="таймаут ожидания готовности фида (секунды)",
    )
    args = parser.parse_args()
    # Если режим передан через CLI, пробросим его в окружение для совместимости
    if getattr(args, "mode", None):
        os.environ["MODE"] = args.mode
    max_seconds = _resolve_seconds(args.max_seconds)
    max_cycles = _resolve_cycles(args.max_cycles)
    skip_feed_check = bool(args.skip_feed_check) or _env_flag("SKIP_FEED_CHECK")
    use_mock_feed = bool(args.use_mock_feed) or _env_flag("USE_MOCK_FEED")
    feed_timeout = args.feed_timeout if args.feed_timeout and args.feed_timeout > 0 else None
    if feed_timeout is None:
        env_feed_timeout = os.getenv("FEED_TIMEOUT")
        if env_feed_timeout:
            try:
                parsed_timeout = float(env_feed_timeout)
                if parsed_timeout > 0:
                    feed_timeout = parsed_timeout
            except ValueError:
                logger.warning("Игнорируем некорректное значение FEED_TIMEOUT=%s", env_feed_timeout)

    try:
        asyncio.run(
            _run_paper_loop(
                max_seconds=max_seconds,
                max_cycles=max_cycles,
                skip_feed_check=skip_feed_check,
                use_mock_feed=use_mock_feed,
                feed_timeout=feed_timeout,
            )
        )
    except KeyboardInterrupt:
        logger.info("Paper runner остановлен пользователем.")


if __name__ == "__main__":
    main()


