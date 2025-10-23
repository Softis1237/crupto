"""Простой Parquet sink для оффлайн-аналитики."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd


class ParquetSink:
    """Сохраняет батчи записей в Parquet-файлы."""

    def __init__(self, base_path: str | Path = "storage/parquet") -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def write(self, name: str, rows: Iterable[Mapping[str, object]]) -> Path:
        """Сохраняет записи в файл `<name>.parquet`."""

        data = list(rows)
        if not data:
            return self.base_path / f"{name}.parquet"
        frame = pd.DataFrame(data)
        path = self.base_path / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        return path


__all__ = ["ParquetSink"]
