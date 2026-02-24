"""
Ingestion pipeline: fetch → enrich → store.

Orchestrates the three stages without knowing the scheduler or API layer.
This clean separation means the pipeline can be triggered from:
  - The scheduler (periodic)
  - The POST /sync endpoint (manual)
  - Tests (directly)
"""

import logging
from datetime import datetime, timedelta, timezone

from config import settings
from enrichment.geo_ip import GeoIPPlugin
from enrichment.tor_classifier import TORClassifierPlugin
from ingestion.fetcher import fetch_alerts
from models import StoredAlert
from storage import alert_repository

logger = logging.getLogger(__name__)

# Enrichment plugins run in order — TOR classifier depends on GeoIP running first
_PLUGINS = [GeoIPPlugin(), TORClassifierPlugin()]


def _default_since() -> datetime:
    """Fallback lookback window used on first startup with no sync history."""
    return datetime.now(timezone.utc) - timedelta(hours=settings.default_lookback_hours)


def _get_since() -> datetime:
    """
    Determine the since timestamp for the upstream fetch.

    Priority:
      1. last_fetched_at from DB — exact resume point after restart
      2. Default lookback window — used on very first startup
    """
    state = alert_repository.get_sync_state()
    raw = state.get("last_fetched_at")
    if raw:
        return datetime.fromisoformat(raw)
    return _default_since()


async def run_sync() -> dict:
    """
    Execute one full sync cycle: fetch → enrich → store.

    Returns a summary dict for the caller to log or return to the API.
    Never raises — catches all exceptions so the scheduler and POST /sync stay resilient.

    Two-layer exception handling (intentional nested try/except):
      Inner except: knows the failure is a fetch error → safely writes status to DB.
      Outer except: last resort — DB itself may be broken, so only logs, no DB write.
    """
    try:
        since = _get_since()
        now = datetime.now(timezone.utc)

        try:
            raw_alerts = await fetch_alerts(since)
        except Exception as exc:  # pylint: disable=broad-except
            error_msg = str(exc)
            logger.error("Upstream fetch failed after all retries: %s", error_msg)
            alert_repository.update_sync_state(last_sync_status="failed", last_error=error_msg)
            return {"status": "failed", "error": error_msg}

        enriched: list[StoredAlert] = []
        for alert in raw_alerts:
            alert_dict = alert.model_dump()

            # Run all plugins in sequence
            for plugin in _PLUGINS:
                alert_dict = plugin.enrich(alert_dict)

            enriched.append(
                StoredAlert(
                    source=alert_dict["source"],
                    severity=alert_dict["severity"],
                    description=alert_dict["description"],
                    created_at=alert_dict["created_at"],
                    ingested_at=now,
                    ip_address=alert_dict["ip_address"],
                    enrichment_type=alert_dict["enrichment_type"],
                )
            )

        inserted = alert_repository.upsert_alerts(enriched)
        alert_repository.update_sync_state(
            last_fetched_at=now,
            last_sync_status="success",
            last_error=None,
        )

        logger.info(
            "Sync complete: fetched=%d enriched=%d inserted=%d skipped=%d",
            len(raw_alerts),
            len(enriched),
            inserted,
            len(enriched) - inserted,
        )
        return {"status": "success", "fetched": len(raw_alerts), "inserted": inserted}

    except Exception as exc:  # pylint: disable=broad-except
        error_msg = str(exc)
        logger.error("Unhandled pipeline error: %s", error_msg)
        return {"status": "failed", "error": error_msg}
