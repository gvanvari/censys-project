"""
Alert DAO.

Orchestrates storage operations — builds filters, manages transactions,
and maps DB rows to domain models. No SQL lives here; see alert_queries.py.
To switch databases, change alert_queries.py and database.py only.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from models import EnrichmentType, Severity, StoredAlert
from storage import alert_queries
from storage.database import db_cursor

logger = logging.getLogger(__name__)


def _build_filters(
    severity: Optional[Severity],
    source: Optional[str],
    enrichment_type: Optional[EnrichmentType],
    since: Optional[datetime],
) -> tuple[list, list]:
    """Build WHERE clause conditions and params from filter arguments."""
    conditions: list = []
    params: list = []

    if severity:
        conditions.append("severity = ?")
        params.append(severity.value)
    if source is not None:
        conditions.append("source = ?")
        params.append(source.lower())
    if enrichment_type:
        conditions.append("enrichment_type = ?")
        params.append(enrichment_type.value)
    if since:
        # Normalise to UTC before comparison. SQLite stores timestamps as
        # plain strings ending in "Z" (e.g. "2026-02-26T02:40:03Z"), so the
        # WHERE clause is a lexicographic comparison. Passing a non-UTC offset
        # like "+05:00" would compare character-by-character against "Z"
        # strings and produce wrong results. Converting to UTC first ensures
        # the strings are always in the same format and sort correctly.
        since_utc = since.astimezone(timezone.utc).replace(tzinfo=None)
        conditions.append("created_at >= ?")
        params.append(since_utc.isoformat() + "Z")

    return conditions, params


def _row_to_alert(row: object) -> StoredAlert:
    """Convert a sqlite3.Row to a StoredAlert model."""
    return StoredAlert(
        id=row["id"],
        source=row["source"],
        severity=Severity(row["severity"]),
        description=row["description"],
        created_at=datetime.fromisoformat(row["created_at"]),
        ingested_at=datetime.fromisoformat(row["ingested_at"]),
        ip_address=row["ip_address"],
        enrichment_type=EnrichmentType(row["enrichment_type"]),
    )


def upsert_alerts(alerts: List[StoredAlert]) -> int:
    """Insert alerts, silently skipping duplicates (same source + created_at)."""
    inserted = 0
    with db_cursor() as cursor:
        for alert in alerts:
            inserted += alert_queries.insert_alert(cursor, alert)
    logger.debug("Upserted %d/%d alerts (rest were duplicates)", inserted, len(alerts))
    return inserted


def list_alerts(
    severity: Optional[Severity] = None,
    source: Optional[str] = None,
    enrichment_type: Optional[EnrichmentType] = None,
    since: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[List[StoredAlert], int]:
    """Return (alerts, total_count) with optional filters."""
    conditions, params = _build_filters(severity, source, enrichment_type, since)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with db_cursor() as cursor:
        total = alert_queries.count_alerts(cursor, where, params)
        rows = alert_queries.query_alerts(cursor, where, params, limit, offset)

    return [_row_to_alert(row) for row in rows], total


def get_sync_state() -> dict:
    """Return the single sync_state row as a plain dict."""
    with db_cursor() as cursor:
        row = alert_queries.fetch_sync_state(cursor)
    return dict(row) if row else {}


def update_sync_state(
    last_fetched_at: Optional[datetime] = None,
    last_sync_status: Optional[str] = None,
    last_error: Optional[str] = None,
) -> None:
    """Update sync checkpoint after each sync attempt."""
    now = datetime.now(timezone.utc).isoformat()
    with db_cursor() as cursor:
        alert_queries.save_sync_state(
            cursor,
            last_fetched_at.isoformat() if last_fetched_at else None,
            last_sync_status,
            last_error,
            now,
        )
