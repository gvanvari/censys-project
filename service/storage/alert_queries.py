"""
Raw SQL queries for alerts and sync_state.

Each function takes a cursor and executes exactly one query.
No business logic, no loops, no conditionals — just SQL.
To switch databases, change this file and database.py only.
"""

import sqlite3
from typing import Any, Optional

from models import StoredAlert


def insert_alert(cursor: sqlite3.Cursor, alert: StoredAlert) -> int:
    """INSERT OR IGNORE one alert. Returns 1 if inserted, 0 if duplicate."""
    cursor.execute(
        """
        INSERT OR IGNORE INTO alerts
            (source, severity, description, created_at, ingested_at, ip_address, enrichment_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            alert.source,
            alert.severity.value,
            alert.description,
            alert.created_at.isoformat(),
            alert.ingested_at.isoformat(),
            alert.ip_address,
            alert.enrichment_type.value,
        ),
    )
    return cursor.rowcount


def count_alerts(cursor: sqlite3.Cursor, where: str, params: list) -> int:
    """Return total number of alerts matching the WHERE clause."""
    cursor.execute(f"SELECT COUNT(*) FROM alerts {where}", params)
    return cursor.fetchone()[0]


def query_alerts(cursor: sqlite3.Cursor, where: str, params: list, limit: int, offset: int) -> list:
    """Return alert rows matching the WHERE clause, newest first."""
    cursor.execute(
        f"SELECT * FROM alerts {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    )
    return cursor.fetchall()


def fetch_sync_state(cursor: sqlite3.Cursor) -> Optional[Any]:
    """Return the single sync_state row, or None if not initialized."""
    cursor.execute("SELECT * FROM sync_state WHERE id = 1")
    return cursor.fetchone()


def save_sync_state(
    cursor: sqlite3.Cursor,
    last_fetched_at: Optional[str],
    last_sync_status: Optional[str],
    last_error: Optional[str],
    updated_at: str,
) -> None:
    """Update the single sync_state row."""
    cursor.execute(
        """
        UPDATE sync_state SET
            last_fetched_at  = COALESCE(?, last_fetched_at),
            last_sync_status = COALESCE(?, last_sync_status),
            last_error       = ?,
            updated_at       = ?
        WHERE id = 1
        """,
        (last_fetched_at, last_sync_status, last_error, updated_at),
    )
