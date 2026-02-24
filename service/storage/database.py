"""
SQLite database initialisation.

Why SQLite:
  - Zero ops — no separate container or process
  - Full SQL with proper schema, indexes, and constraints
  - Ships with Python stdlib
  - DAO layer abstracts it so swapping to PostgreSQL is a connection string change

Two tables:
  - alerts      — normalised + enriched alerts
  - sync_state  — single-row checkpoint so restarts resume from where we left off
"""

import logging
import sqlite3
from contextlib import contextmanager
from typing import Generator

from config import settings

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory set for dict-like access."""
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """Context manager: yields a cursor and commits on clean exit, rolls back on error."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables and indexes if they don't exist. Safe to call on every startup."""
    with db_cursor() as cursor:
        # WAL mode persists at the file level — only needs to be set once
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                source          TEXT NOT NULL,
                severity        TEXT NOT NULL,
                description     TEXT,
                created_at      TEXT NOT NULL,
                ingested_at     TEXT NOT NULL,
                ip_address      TEXT NOT NULL,
                enrichment_type TEXT NOT NULL,
                UNIQUE(source, created_at)
            );

            CREATE INDEX IF NOT EXISTS idx_alerts_severity    ON alerts(severity);
            CREATE INDEX IF NOT EXISTS idx_alerts_source      ON alerts(source);
            CREATE INDEX IF NOT EXISTS idx_alerts_created_at  ON alerts(created_at);
            CREATE INDEX IF NOT EXISTS idx_alerts_ingested_at ON alerts(ingested_at);

            CREATE TABLE IF NOT EXISTS sync_state (
                id               INTEGER PRIMARY KEY CHECK (id = 1),
                last_fetched_at  TEXT,
                last_sync_status TEXT,
                last_error       TEXT,
                updated_at       TEXT
            );

            INSERT OR IGNORE INTO sync_state (id) VALUES (1);
        """
        )
    logger.info("Database initialised at %s", settings.db_path)


def check_db_connection() -> bool:
    """Lightweight connectivity check used by /health endpoint."""
    try:
        with db_cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("DB connectivity check failed: %s", exc)
        return False
