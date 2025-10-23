"""DAO слой для работы с SQLite хранилищем."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional


@dataclass(slots=True)
class OrderPayload:
    ts: int
    symbol: str
    side: str
    order_type: str
    qty: float
    price: float | None
    status: str
    client_id: str
    exchange_id: str
    meta: dict[str, Any] | None = None
    run_id: str | None = None


@dataclass(slots=True)
class TradePayload:
    order_id: int
    ts: int
    symbol: str
    side: str
    qty: float
    price: float
    fee: float = 0.0
    pnl_r: float = 0.0
    meta: dict[str, Any] | None = None
    run_id: str | None = None


@dataclass(slots=True)
class PositionPayload:
    symbol: str
    ts: int
    qty: float
    avg_price: float
    unrealized_pnl_r: float
    realized_pnl_r: float
    exposure_usd: float
    meta: dict[str, Any] | None = None
    run_id: str | None = None


@dataclass(slots=True)
class EquitySnapshotPayload:
    ts: int
    equity_usd: float
    pnl_r_cum: float
    max_dd_r: float
    exposure_gross: float
    exposure_net: float
    run_id: str | None = None


@dataclass(slots=True)
class LatencyPayload:
    ts: int
    stage: str
    ms: float
    run_id: str | None = None


class PersistDAO:
    """Обёртка над SQLite со схемой проекта."""

    def __init__(self, db_path: str | Path = "storage/crupto.db", run_id: str | None = None) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.schema_path = Path(__file__).with_name("schema.sql")
        self.run_id = run_id or os.getenv("RUN_ID")

    def _resolve_run_id(self, provided: str | None) -> str:
        value = provided or self.run_id
        if not value:
            raise ValueError("run_id is required for persistence operations.")
        return value

    def initialize(self) -> None:
        """Создаёт таблицы согласно схеме."""

        with self._connect() as conn, self.schema_path.open("r", encoding="utf-8") as handle:
            conn.executescript(handle.read())

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path.as_posix(), isolation_level=None, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        raw_meta = data.get("meta_json")
        if raw_meta is not None:
            try:
                data["meta"] = json.loads(raw_meta)
            except (TypeError, json.JSONDecodeError):
                data["meta"] = None
        return data

    def _rows_to_dicts(self, rows: Iterable[sqlite3.Row]) -> List[Dict[str, Any]]:
        return [self._row_to_dict(row) for row in rows]

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Контекстный менеджер транзакции."""

        conn = self._connect()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def insert_order(self, payload: OrderPayload) -> int:
        """Вставляет заявку, обеспечивая идемпотентность по client_id."""

        run_id = self._resolve_run_id(payload.run_id)
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO orders
                (ts, symbol, side, type, qty, price, status, client_id, exchange_id, run_id, meta_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.ts,
                    payload.symbol,
                    payload.side,
                    payload.order_type,
                    payload.qty,
                    payload.price,
                    payload.status,
                    payload.client_id,
                    payload.exchange_id,
                    run_id,
                    json.dumps(payload.meta, ensure_ascii=False) if payload.meta else None,
                ),
            )
            if cursor.rowcount == 0:
                row = conn.execute(
                    "SELECT id FROM orders WHERE client_id = ? AND run_id = ?",
                    (payload.client_id, run_id),
                ).fetchone()
                return int(row["id"])
            order_id = int(cursor.lastrowid)
            return order_id

    def update_order_status(
        self,
        client_id: str,
        *,
        status: str,
        price: float | None = None,
        qty: float | None = None,
        meta: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> None:
        """��������� ������ ������ �� client_id."""

        updates: List[str] = ["status = ?", "updated_at = strftime('%s','now')"]
        params: List[Any] = [status]
        if price is not None:
            updates.append("price = ?")
            params.append(price)
        if qty is not None:
            updates.append("qty = ?")
            params.append(qty)
        if meta is not None:
            updates.append("meta_json = ?")
            params.append(json.dumps(meta, ensure_ascii=False))
        resolved_run_id = self._resolve_run_id(run_id)
        params.extend([client_id, resolved_run_id])

        with self.transaction() as conn:
            conn.execute("UPDATE orders SET {} WHERE client_id = ? AND run_id = ?".format(', '.join(updates)), params)

    def fetch_order_by_client(self, client_id: str, run_id: str | None = None) -> Optional[Dict[str, Any]]:
        """Возвращает заказ по client_id."""

        resolved_run_id = self._resolve_run_id(run_id)
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM orders WHERE client_id = ? AND run_id = ?", (client_id, resolved_run_id)).fetchone()
        return dict(row) if row else None

    def upsert_position(self, payload: PositionPayload) -> None:
        """Обновляет запись о позиции."""

        run_id = self._resolve_run_id(payload.run_id)
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO positions(symbol, run_id, ts, qty, avg_price, unrealized_pnl_r, realized_pnl_r, exposure_usd, meta_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, run_id) DO UPDATE SET
                    ts = excluded.ts,
                    qty = excluded.qty,
                    avg_price = excluded.avg_price,
                    unrealized_pnl_r = excluded.unrealized_pnl_r,
                    realized_pnl_r = excluded.realized_pnl_r,
                    exposure_usd = excluded.exposure_usd,
                    meta_json = excluded.meta_json
                """,
                (
                    payload.symbol,
                    run_id,
                    payload.ts,
                    payload.qty,
                    payload.avg_price,
                    payload.unrealized_pnl_r,
                    payload.realized_pnl_r,
                    payload.exposure_usd,
                    json.dumps(payload.meta, ensure_ascii=False) if payload.meta else None,
                ),
            )

    def insert_trade(self, payload: TradePayload) -> int:
        """��������� ��?������ �� �?���?�?���%����'."""

        run_id = self._resolve_run_id(payload.run_id)
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO trades
                (order_id, ts, symbol, side, qty, price, fee, pnl_r, run_id, meta_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.order_id,
                    payload.ts,
                    payload.symbol,
                    payload.side,
                    payload.qty,
                    payload.price,
                    payload.fee,
                    payload.pnl_r,
                    run_id,
                    json.dumps(payload.meta, ensure_ascii=False) if payload.meta else None,
                ),
            )
            return int(cursor.lastrowid)

    def insert_equity_snapshot(self, payload: EquitySnapshotPayload) -> None:
        """������� equity � ��-����."""

        run_id = self._resolve_run_id(payload.run_id)
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO equity_snapshots
                (ts, run_id, equity_usd, pnl_r_cum, max_dd_r, exposure_gross, exposure_net)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.ts,
                    run_id,
                    payload.equity_usd,
                    payload.pnl_r_cum,
                    payload.max_dd_r,
                    payload.exposure_gross,
                    payload.exposure_net,
                ),
            )

    def insert_latency(self, payload: LatencyPayload) -> None:
        """���࠭�� ����৭�� ��������."""

        run_id = self._resolve_run_id(payload.run_id)
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO latency (ts, stage, ms, run_id)
                VALUES (?, ?, ?, ?)
                """,
                (payload.ts, payload.stage, payload.ms, run_id),
            )

    def fetch_latency(self, limit: int | None = None, run_id: str | None = None) -> List[Dict[str, Any]]:
        """�����র���� ������� latency."""

        resolved_run_id = self._resolve_run_id(run_id)
        query = "SELECT * FROM latency WHERE run_id = ? ORDER BY ts DESC"
        params: List[Any] = [resolved_run_id]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


    def fetch_orders(
        self,
        *,
        run_id: str | None = None,
        limit: int | None = None,
        status: str | None = None,
        symbol: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Return orders for the specified run."""

        resolved_run_id = self._resolve_run_id(run_id)
        query = ["SELECT * FROM orders WHERE run_id = ?"]
        params: List[Any] = [resolved_run_id]
        if status:
            query.append("AND status = ?")
            params.append(status)
        if symbol:
            query.append("AND symbol = ?")
            params.append(symbol)
        query.append("ORDER BY ts DESC, id DESC")
        if limit is not None:
            query.append("LIMIT ?")
            params.append(limit)
        sql = " ".join(query)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return self._rows_to_dicts(rows)

    def fetch_trades(
        self,
        *,
        run_id: str | None = None,
        limit: int | None = None,
        symbol: str | None = None,
        order_id: int | None = None,
    ) -> List[Dict[str, Any]]:
        """Return trades for the specified run."""

        resolved_run_id = self._resolve_run_id(run_id)
        query = ["SELECT * FROM trades WHERE run_id = ?"]
        params: List[Any] = [resolved_run_id]
        if symbol:
            query.append("AND symbol = ?")
            params.append(symbol)
        if order_id is not None:
            query.append("AND order_id = ?")
            params.append(order_id)
        query.append("ORDER BY ts DESC, id DESC")
        if limit is not None:
            query.append("LIMIT ?")
            params.append(limit)
        sql = " ".join(query)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return self._rows_to_dicts(rows)

    def fetch_positions(self, *, run_id: str | None = None) -> List[Dict[str, Any]]:
        """Return open positions for the specified run."""

        resolved_run_id = self._resolve_run_id(run_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM positions WHERE run_id = ? ORDER BY ts DESC",
                (resolved_run_id,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def fetch_position(self, symbol: str, *, run_id: str | None = None) -> Optional[Dict[str, Any]]:
        """Return a single position by symbol."""

        resolved_run_id = self._resolve_run_id(run_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM positions WHERE symbol = ? AND run_id = ?",
                (symbol, resolved_run_id),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def clear_position(self, symbol: str, *, run_id: str | None = None) -> None:
        """Delete a position for the specified run."""

        resolved_run_id = self._resolve_run_id(run_id)
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM positions WHERE symbol = ? AND run_id = ?",
                (symbol, resolved_run_id),
            )

    def fetch_equity_last(self, run_id: str | None = None) -> Optional[Dict[str, Any]]:
        """���������� ��������� equity snapshot."""

        resolved_run_id = self._resolve_run_id(run_id)
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM equity_snapshots WHERE run_id = ? ORDER BY ts DESC LIMIT 1", (resolved_run_id,)).fetchone()
        return dict(row) if row else None

    def fetch_equity_history(self, limit: int | None = None, run_id: str | None = None) -> List[Dict[str, Any]]:
        """���������� ������� equity."""

        resolved_run_id = self._resolve_run_id(run_id)
        query = "SELECT * FROM equity_snapshots WHERE run_id = ? ORDER BY ts DESC"
        params: List[Any] = [resolved_run_id]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

