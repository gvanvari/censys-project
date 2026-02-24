"""
Sync scheduler using APScheduler.

APScheduler's AsyncIOScheduler integrates cleanly with FastAPI's async event
loop — no threads required for an I/O-bound polling job.

Concurrency guard:
  asyncio.Lock prevents two syncs from running simultaneously (e.g., the
  scheduler fires while a manual POST /sync is already in progress).

  In a multi-instance deployment this lock would be replaced with a
  distributed lock (Redis SETNX) or a dedicated job queue.
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import settings
from ingestion.pipeline import run_sync

logger = logging.getLogger(__name__)

_sync_lock = asyncio.Lock()  # initialized, not locked yet
scheduler = AsyncIOScheduler()


async def _sync_if_idle() -> None:
    """Run sync only if no other sync is currently in progress."""
    if _sync_lock.locked():
        logger.info("Sync skipped — previous sync still running")
        return
    async with _sync_lock:  # acquire and release lock
        await run_sync()


async def trigger_sync() -> dict:
    """
    Called by POST /sync to trigger an immediate manual sync.

    Returns quickly — sync runs in a background task so the HTTP response
    is not blocked by the sync duration.
    """
    if _sync_lock.locked():
        return {"status": "conflict", "message": "Sync already in progress"}

    asyncio.create_task(_sync_if_idle())
    return {"status": "sync_triggered", "message": "Sync started in background"}


def start_scheduler() -> None:
    """Start the background polling scheduler. Called once on app startup."""
    scheduler.add_job(
        _sync_if_idle,
        trigger="interval",
        seconds=settings.sync_interval_seconds,
        id="periodic_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started (interval=%ds)", settings.sync_interval_seconds)


def stop_scheduler() -> None:
    """Gracefully stop the scheduler. Called on app shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
