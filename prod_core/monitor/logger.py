"""Конфигурация логгирования для прод-ядра."""

from __future__ import annotations

import os
from pathlib import Path

from loguru import logger


def configure_logging(log_level: str | None = None, log_dir: str | None = None) -> None:
    """Настраивает loguru на вывод в STDOUT и файл."""

    logger.remove()
    level = (log_level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logger.add(lambda msg: print(msg, end=""), level=level, colorize=True, backtrace=False, diagnose=False)

    if log_dir:
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        logger.add(
            path / "crupto.log",
            level=level,
            rotation="7 days",
            retention="14 days",
            compression="zip",
        )
