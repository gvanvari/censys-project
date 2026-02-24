"""
FastAPI application entry point.

Startup sequence (via lifespan):
  1. Init DB tables (idempotent — safe to run on every start)
  2. Read last_fetched_at from DB to determine resume point
  3. Run one immediate sync to catch up since last shutdown
  4. Start APScheduler for periodic polling

This ensures the service is never "cold" after a restart — it immediately
resumes from where it left off.
"""

import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from api.routes import router
from config import settings
from fastapi import FastAPI
from ingestion.pipeline import run_sync
from ingestion.scheduler import start_scheduler, stop_scheduler
from storage.database import init_db

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manage startup and shutdown lifecycle."""
    logger.info("Starting Censys Alert Ingestion Service")

    init_db()

    logger.info("Running initial sync on startup...")
    result = await run_sync()
    logger.info("Initial sync result: %s", result)

    start_scheduler()

    yield  # Application runs here

    stop_scheduler()
    logger.info("Service shutdown complete")


app = FastAPI(
    title="Censys Alert Ingestion Service",
    description=(
        "Periodically fetches alerts from an upstream SIEM aggregator, "
        "enriches them with GeoIP and TOR classification, and exposes a "
        "normalized REST API for downstream consumers."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
