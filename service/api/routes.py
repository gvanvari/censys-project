import logging
from datetime import datetime
from typing import Optional

from config import settings
from fastapi import APIRouter, HTTPException, Query
from ingestion.scheduler import trigger_sync
from models import (
    AlertListResponse,
    EnrichmentType,
    HealthResponse,
    HealthStatus,
    Severity,
    SyncResponse,
)
from storage import alert_repository
from storage.database import check_db_connection

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/alerts", response_model=AlertListResponse)
def list_alerts(
    severity: Optional[Severity] = Query(None, description="Filter by severity level"),
    source: Optional[str] = Query(None, description="Filter by source system"),
    enrichment_type: Optional[EnrichmentType] = Query(
        None, description="Filter by enrichment classification"
    ),
    since: Optional[datetime] = Query(
        None, description="Return alerts created after this ISO8601 timestamp"
    ),
    limit: int = Query(100, ge=1, le=500, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Returns normalized alerts from the local database.

    All filters are optional and combinable.
    `limit` is capped at 500 to prevent accidental full-table dumps (DoS mitigation).
    """
    alerts, total = alert_repository.list_alerts(
        severity=severity,
        source=source,
        enrichment_type=enrichment_type,
        since=since,
        limit=limit,
        offset=offset,
    )
    return AlertListResponse(total=total, limit=limit, offset=offset, alerts=alerts)


@router.post("/sync", response_model=SyncResponse, status_code=202)
async def manual_sync():
    """
    Triggers an immediate fetch from the upstream Alerts API.

    Returns 202 Accepted immediately — the sync runs in the background.
    Returns 409 Conflict if a sync is already in progress.

    Why 202 and not 200:
      The sync hasn't completed when we respond. 202 Accepted means
      "request received, processing has begun" — the correct HTTP semantic
      for async operations.

    Note on error exposure:
      This is an internal service API. Returning specific status codes
      (409) is appropriate. For a public API, we'd return vague 400s.
    """
    result = await trigger_sync()

    if result["status"] == "conflict":
        raise HTTPException(status_code=409, detail=result["message"])

    return SyncResponse(status=result["status"], message=result["message"])


@router.get("/health", response_model=HealthResponse)
def health():
    """
    Lightweight health check. Does NOT call the upstream API.

    Why not call upstream here:
      Health checks are polled frequently by load balancers and monitoring.
      Calling upstream on every health check would inflate their rate limits
      and cause false "down" reports when upstream is slow but we're healthy.
      Upstream reachability is captured by last_sync_status from actual syncs.

    Status semantics:
      ok       — DB reachable, last sync succeeded
      degraded — DB reachable but last sync failed (upstream issue)
      down     — DB not reachable (our service is broken)
    """
    db_ok = check_db_connection()

    if not db_ok:
        return HealthResponse(
            status=HealthStatus.down,
            db_connected=False,
            sync_interval_seconds=settings.sync_interval_seconds,
            upstream_url=settings.upstream_url,
        )

    state = alert_repository.get_sync_state()
    last_status = state.get("last_sync_status")
    last_fetched_raw = state.get("last_fetched_at")
    last_fetched = datetime.fromisoformat(last_fetched_raw) if last_fetched_raw else None

    overall_status = HealthStatus.ok if last_status == "success" else HealthStatus.degraded

    return HealthResponse(
        status=overall_status,
        db_connected=True,
        last_successful_sync=last_fetched if last_status == "success" else None,
        last_sync_status=last_status,
        last_error=state.get("last_error"),
        sync_interval_seconds=settings.sync_interval_seconds,
        upstream_url=settings.upstream_url,
    )
