PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    type TEXT NOT NULL,
    qty REAL NOT NULL,
    price REAL,
    status TEXT NOT NULL,
    client_id TEXT NOT NULL,
    exchange_id TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT 'legacy',
    meta_json TEXT,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
    UNIQUE(client_id, run_id)
);
CREATE INDEX IF NOT EXISTS idx_orders_ts ON orders(ts);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_run ON orders(run_id);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    ts INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    price REAL NOT NULL,
    fee REAL DEFAULT 0,
    pnl_r REAL DEFAULT 0,
    run_id TEXT NOT NULL DEFAULT 'legacy',
    meta_json TEXT,
    FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_trades_ts ON trades(ts);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_order ON trades(order_id);
CREATE INDEX IF NOT EXISTS idx_trades_run ON trades(run_id);

CREATE TABLE IF NOT EXISTS positions (
    symbol TEXT NOT NULL,
    run_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    qty REAL NOT NULL,
    avg_price REAL NOT NULL,
    unrealized_pnl_r REAL DEFAULT 0,
    realized_pnl_r REAL DEFAULT 0,
    exposure_usd REAL DEFAULT 0,
    meta_json TEXT,
    PRIMARY KEY(symbol, run_id)
);
CREATE INDEX IF NOT EXISTS idx_positions_ts ON positions(ts);
CREATE INDEX IF NOT EXISTS idx_positions_run ON positions(run_id);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    ts INTEGER NOT NULL,
    run_id TEXT NOT NULL,
    equity_usd REAL NOT NULL,
    pnl_r_cum REAL NOT NULL,
    max_dd_r REAL NOT NULL,
    exposure_gross REAL NOT NULL,
    exposure_net REAL NOT NULL,
    PRIMARY KEY(ts, run_id)
);

CREATE TABLE IF NOT EXISTS latency (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    stage TEXT NOT NULL,
    ms REAL NOT NULL,
    run_id TEXT NOT NULL DEFAULT 'legacy'
);
CREATE INDEX IF NOT EXISTS idx_latency_ts ON latency(ts);
CREATE INDEX IF NOT EXISTS idx_latency_stage ON latency(stage);
CREATE INDEX IF NOT EXISTS idx_latency_run ON latency(run_id);

