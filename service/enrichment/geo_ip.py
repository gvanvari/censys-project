"""
GeoIP enrichment plugin.

Adds a randomized public IP address to each alert.

Production equivalent:
  Would call whois to return the real source IP
  and ASN data associated with the alert's origin. The interface stays
  identical — only this file changes.

Why public IPs only:
  RFC1918 private ranges (10.x, 172.16-31.x, 192.168.x) are internal
  network addresses and would not appear as threat actor IPs in a real
  SIEM alert enrichment context.
"""

import random

from enrichment.base import EnrichmentPlugin

# RFC1918 private ranges to exclude from random generation
_PRIVATE_PREFIXES = (
    "10.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
    "192.168.",
    "127.",
    "169.254.",
)


def _random_public_ip() -> str:
    """Generate a random public IPv4 address, excluding RFC1918 ranges."""
    while True:
        ip = ".".join(str(random.randint(1, 254)) for _ in range(4))
        if not any(ip.startswith(prefix) for prefix in _PRIVATE_PREFIXES):
            return ip


class GeoIPPlugin(EnrichmentPlugin):
    """Enriches alerts with a simulated source IP address."""

    def enrich(self, alert: dict) -> dict:
        alert["ip_address"] = _random_public_ip()
        return alert
