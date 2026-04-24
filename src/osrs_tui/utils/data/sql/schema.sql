-- -----------------------------------------------------------------------
-- Wealth Tracking
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wealth_snapshots (
    id          INTEGER PRIMARY KEY,
    username    TEXT    NOT NULL,
    recorded_at TEXT    NOT NULL,
    note        TEXT,
    total_value INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bank_items (
    id          INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES wealth_snapshots(id) ON DELETE CASCADE,
    item_name   TEXT    NOT NULL,
    quantity    INTEGER NOT NULL DEFAULT 1,
    unit_price  INTEGER NOT NULL DEFAULT 0,
    total_value INTEGER GENERATED ALWAYS AS (quantity * unit_price) STORED
);

CREATE INDEX IF NOT EXISTS idx_bank_snapshot ON bank_items(snapshot_id);

-- -----------------------------------------------------------------------
-- Grand Exchange transactions
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ge_transactions (
    id              INTEGER PRIMARY KEY,
    username        TEXT    NOT NULL,
    recorded_at     TEXT    NOT NULL,
    item_name       TEXT    NOT NULL,
    transaction_type TEXT   NOT NULL CHECK(transaction_type IN ('buy', 'sell')),
    quantity        INTEGER NOT NULL,
    price_each      INTEGER NOT NULL,
    total_value     INTEGER GENERATED ALWAYS AS (quantity * price_each) STORED,
    note            TEXT
);

CREATE INDEX IF NOT EXISTS idx_ge_user ON ge_transactions(username, recorded_at);
