"""
Pydantic models — the data contracts for the service.

Separating models from routes lets us reuse schemas across the API,
the storage layer, and tests without circular imports.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class EnrichmentType(str, Enum):
    tor_exit_node = "tor_exit_node"
    clean = "clean"


# ── Upstream contract (what the mock API returns) ────────────────────────────


class UpstreamAlert(BaseModel):
    """Matches the mock API response schema exactly."""

    source: str
    severity: Severity
    description: str
    created_at: datetime


class UpstreamAlertsResponse(BaseModel):
    alerts: List[UpstreamAlert]


# ── Stored / enriched alert (what we persist in SQLite) ──────────────────────


class StoredAlert(BaseModel):
    """Normalized + enriched alert as stored in DB."""

    id: Optional[int] = None
    source: str
    severity: Severity
    description: str
    created_at: datetime
    ingested_at: datetime
    ip_address: str
    enrichment_type: EnrichmentType


# ── API response models ───────────────────────────────────────────────────────


class AlertListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    has_more: bool
    alerts: List[StoredAlert]


class SyncResponse(BaseModel):
    status: str
    message: str


class HealthStatus(str, Enum):
    ok = "ok"
    degraded = "degraded"
    down = "down"


class HealthResponse(BaseModel):
    status: HealthStatus
    db_connected: bool
    last_successful_sync: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_error: Optional[str] = None
    sync_interval_seconds: int
    upstream_url: str
