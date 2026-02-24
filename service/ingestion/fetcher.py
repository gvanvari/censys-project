"""
Upstream API fetcher with retry and exponential backoff.

Uses tenacity rather than manual retry logic

Retry strategy:
  - Up to 3 attempts
  - Exponential backoff: 1s, 2s, 4s (with jitter to prevent retry storms)
  - Only retries on 5xx and network errors — 4xx means WE sent a bad request,
    so retrying won't help
"""

import logging
from datetime import datetime

import httpx
from config import settings
from models import UpstreamAlert
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """
    Retry on network errors and 5xx responses.
    Do NOT retry on 4xx — those are client errors (our bug, not upstream's).
    """
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.NetworkError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=8),
    retry=retry_if_exception(_is_retryable),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def fetch_alerts(since: datetime) -> list[UpstreamAlert]:
    """
    Fetch alerts from the upstream API since the given timestamp.

    Raises the last exception if all retries are exhausted.
    The caller (pipeline) is responsible for handling the final failure gracefully.
    """
    since_str = since.isoformat().replace("+00:00", "Z")
    url = f"{settings.upstream_url}/alerts"

    logger.info("Fetching alerts from upstream (since=%s)", since_str)

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params={"since": since_str})
        response.raise_for_status()

    data = response.json()
    alerts = [UpstreamAlert(**alert) for alert in data.get("alerts", [])]
    logger.info("Received %d alerts from upstream", len(alerts))
    return alerts
