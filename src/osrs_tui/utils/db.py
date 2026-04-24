"""
utils/db.py - SQLite persistence layer for the OSRS TUI.

All tables are created here. The module exposes a single `get_db()` call
that restuns a thread-local connection (safe for Textual's worker threads).

Schema overview
---------------
wealth_snapshots        - timstamped total wealth entries
bank_items              - line items belonging to a snapshot
ge_transactions         - Grand Exchange buy/sell records

Design notes
------------
+ All monetary values are stored as INTEGER (coins)
+ ISO-8601 timestamps (TEXT) so they sort lexicographically.
+ No ORM - plain sqlite3 for zero extra dependencies.
+ Every table has an `id INTEGER PRIMARY KEY` so so future JOINs are trivial.
+ The schema is intentionally additive-only: new columns/tables are always
    added via ALTER TABLE / CREATE TABLE IF NOT EXISTS so existing data is
    never lost on upgrade.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_DB_DIR = Path.home() / ".local" / "share" / "osrs-tui"
DB_PATH = _DB_DIR / "osrs_tui.db"
SQL_PATH = Path(__file__).parent / "data" / "sql"
if not SQL_PATH.exists():
    SQL_PATH.mkdir(parents=False, exist_ok=True)

_local = threading.local()


def get_db() -> sqlite3.Connection:
    """Return a thread-local SQLite connection, creating it if necessary."""
    if not hasattr(_local, "conn"):
        _DB_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _create_schema(conn)
        _local.conn = conn
    return _local.conn


def _create_schema(conn: sqlite3.Connection) -> None:
    sql_path = SQL_PATH / "schema.sql"
    with open(sql_path, "r") as file:
        sql = file.read()
    conn.executescript(sql)
    conn.commit()


def save_snapshot(
    username: str,
    items: list[dict],
    note: str = ""
) -> int:
    """Insert a new wealth snapshot and its bank items. Returns snapshot id."""
    conn = get_db()
    now = _now()
    total = sum(i["qty"] * i["price"] for i in items)
    cur = conn.execute(
        "INSERT INTO wealth_snapshots (username, recorded_at, note, total_value) VALUES (?, ?, ?, ?)",
        (username, now, note, total)
    )
    snapshot_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO bank_items (snapshot_id, item_name, quantity, unit_price) VALUES (?, ?, ?, ?)",
        [(snapshot_id, i["name"], i["qty"], i["price"]) for i in items]
    )
    conn.commit()
    return snapshot_id


def get_snapshots(username: str) -> list[sqlite3.Row]:
    """Return all wealth snapshots for a user, newest first."""
    return get_db().execute(
        "SELECT * FROM wealth_snapshots WHERE username=? ORDER BY recorded_at DESC",
        (username,)
    ).fetchall()


def get_snapshot_items(snapshot_id: int) -> list[sqlite3.Row]:
    return get_db().execute(
        "SELECT * FROM bank_items WHERE snapshot_id=? ORDER BY total_value DESC",
        (snapshot_id,)
    ).fetchall()


def delete_snapshot(snapshot_id: int) -> None:
    conn = get_db()
    conn.execute("DELETE FROM wealth_snapshots WHERE id=?", (snapshot_id,))
    conn.commit()


# -----------------------------------------------------------------------
# GE Transactions
# -----------------------------------------------------------------------

def save_ge_transaction(
    username: str,
    item_name: str,
    tx_type: str,
    quantity: int,
    price_each: int,
    note: str = ""
) -> int:
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO ge_transactions
            (username, recorded_at, item_name, transaction_type, quantity, price_each, note)
            VALUES (?,?,?,?,?,?,?)""",
        (username, _now(), item_name, tx_type, quantity, price_each, note)
    )
    conn.commit()
    return cur.lastrowid


def get_ge_transactions(username: str, limit: int = 200) -> list[sqlite3.Row]:
    return get_db().execute(
        """SELECT * FROM ge_transactions WHERE username=?
           ORDER BY recorded_at DESC LIMIT ?""",
        (username, limit)
    ).fetchall()


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------
# Analytics queries
# ---------------

def get_wealth_history(username: str) -> list[sqlite3.Row]:
    """
    Return all snapshots as (recorded_at, total_value) ordered oldest -> newest.
    This is the time-series used to plot the wealth sparkline.
    """
    return get_db().execute(
        """
    SELECT recorded_at, total_value
    FROM wealth_snapshots
    WHERE username=?
    ORDER BY recorded_at ASC""",
        (username,)
    ).fetchall()


def get_ge_summary(username: str) -> dict:
    """
    Aggregate GE stats for a user:
        total_spent     - sum of all buy totals
        total_earned    - sum of all sell totals
        net_profit      - earned - spent
        tx_count        - total number of transactions
        top_items       - list of (item_name, net) sorted by |net| desc (top 10)
    """
    conn = get_db()

    agg = conn.execute(
        """SELECT
                COALESCE(SUM(CASE WHEN transaction_type='buy'  THEN total_value ELSE 0 END), 0) AS total_spent,
                COALESCE(SUM(CASE WHEN transaction_type='sell' THEN total_value ELSE 0 END), 0) AS total_earned,
                COUNT(*) AS tx_count
           FROM ge_transactions
           WHERE username=?""",
        (username,)
    ).fetchone()

    top_items = conn.execute(
        """SELECT
                item_name,
                SUM(CASE WHEN transaction_type='sell' THEN  total_value ELSE 0 END) -
                SUM(CASE WHEN transaction_type='buy'  THEN  total_value ELSE 0 END) AS net
           FROM ge_transactions
           WHERE username=?
           GROUP BY item_name
           ORDER BY ABS(net) DESC
           LIMIT 10""",
        (username,)
    ).fetchall()

    return {
        "total_spent": agg["total_spent"],
        "total_earned": agg["total_earned"],
        "net_profit": agg["total_earned"] - agg["total_spent"],
        "tx_count": agg["tx_count"],
        "top_items": [dict(r) for r in top_items],
    }


def get_wealth_delta(username: str) -> dict:
    """
    Return wealth change metrics:
        latest          - most recent `total_value` (or 0)
        previous        - second-most-recent `total_value` (or 0)
        delta           - latest - previous
        snapshot_count  - how many snapshots exist
    """
    rows = get_db().execute(
        """SELECT total_value FROM wealth_snapshots
           WHERE username=?
           ORDER BY recorded_at DESC
           LIMIT 2""",
        (username,)
    ).fetchall()

    latest = rows[0]["total_value"] if len(rows) > 0 else 0
    previous = rows[1]["total_value"] if len(rows) > 1 else 0

    snap_count = get_db().execute(
        "SELECT COUNT(*) FROM wealth_snapshots WHERE username=?",
        (username,)
    ).fetchone()[0]

    return {
        "latest": latest,
        "previous": previous,
        "delta": latest - previous,
        "snapshot_count": snap_count,
    }


def get_ge_monthly_flow(username: str) -> list[dict]:
    """
    Return monthly buy/sell totals for the last 12 months, oldest first.
    Each row: {month: "YYYY-MM", spent: int, earned: int}
    Used for the bar chart in the dashboard.
    """
    rows = get_db().execute(
        """SELECT
                SUBSTR(recorded_at, 1, 7) AS month,
                SUM(CASE WHEN transaction_type='buy'  THEN total_value ELSE 0 END) AS spent,
                SUM(CASE WHEN transaction_type='sell' THEN total_value ELSE 0 END) AS earned
           FROM ge_transactions
           WHERE username=?
           GROUP BY month
           ORDER BY month ASC
           LIMIT 12""",
        (username,)
    ).fetchall()
    return [dict(r) for r in rows]