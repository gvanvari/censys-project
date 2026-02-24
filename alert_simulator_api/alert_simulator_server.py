import logging
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from flask import Flask, Response, jsonify, request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

FAILURE_RATE = float(os.getenv("MOCK_FAILURE_RATE", "0.20"))

SOURCES = [
    "mock-splunk",
    "mock-qradar",
    "mock-xsoar",
    "mock-sentinel",
    "mock-crowdstrike-edr",
    "mock-defender-cloud",
    "mock-suricata",
    "mock-zeek-nta",
    "mock-syslog-core",
    "mock-netflow-border",
]

SEVERITIES = ["low", "medium", "high", "critical"]

DESCRIPTIONS = [
    "Suspicious login from unknown IP",
    "Brute force attempt detected",
    "Lateral movement detected",
    "Data exfiltration pattern observed",
    "Malware signature matched",
    "Privilege escalation attempt",
    "Unusual outbound traffic volume",
    "Port scan detected from internal host",
    "Failed authentication spike",
    "Ransomware behavior pattern detected",
]


def _random_alert(created_after: Optional[datetime] = None) -> dict:
    """Generate a random alert, clamped to the since filter."""
    now = datetime.now(timezone.utc)
    offset_seconds = random.randint(0, 7200)
    created_at = now.replace(microsecond=0) - timedelta(seconds=offset_seconds)
    if created_after:
        created_at = max(created_after, created_at)

    return {
        "source": random.choice(SOURCES),
        "severity": random.choice(SEVERITIES),
        "description": random.choice(DESCRIPTIONS),
        "created_at": created_at.isoformat().replace("+00:00", "Z"),
    }


@app.route("/health")
def health() -> tuple[Response, int]:
    return jsonify({"status": "ok"}), 200


@app.route("/alerts")
def get_alerts() -> tuple[Response, int]:
    """
    GET /alerts?since=<ISO8601>

    Returns a random batch of alerts created after `since`.
    Randomly returns HTTP 500 at the configured failure rate to simulate
    upstream instability — this is what our service must be resilient to.
    """
    if random.random() < FAILURE_RATE:
        logger.warning("Simulating upstream failure (500)")
        return jsonify({"error": "upstream_unavailable", "message": "Service temporarily unavailable"}), 500

    since_param = request.args.get("since")
    since_dt: Optional[datetime] = None

    if since_param:
        try:
            since_dt = datetime.fromisoformat(since_param.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "invalid_since", "message": "since must be ISO8601"}), 400

    alerts = [_random_alert(created_after=since_dt) for _ in range(5)]

    logger.info("Returning %d alerts (since=%s)", len(alerts), since_param)
    return jsonify({"alerts": alerts}), 200


if __name__ == "__main__":
    port = int(os.getenv("MOCK_PORT", "9000"))
    logger.info("Starting mock Alerts API on port %d (failure_rate=%.0f%%)", port, FAILURE_RATE * 100)
    app.run(host="0.0.0.0", port=port)
