"""
TOR exit node classifier enrichment plugin.

Classifies the alert's IP as a known TOR exit node or clean traffic.

Production equivalent:
  Would fetch the Tor Project's bulk exit node list periodically and cache it:
    GET https://check.torproject.org/torbulkexitlist
  Returns plain text, one IP per line. The list would be refreshed every few
  hours

Simulation approach:
  A hardcoded set of realistic-looking IPs acts as the "cached" exit node list.
  The classify() function mirrors the exact logic of the production version.
"""

from enrichment.base import EnrichmentPlugin
from enrichment.sim_constants import MOCK_TOR_EXIT_NODES

# Alias kept for backward compatibility (tests import _MOCK_TOR_EXIT_NODES)
_MOCK_TOR_EXIT_NODES = MOCK_TOR_EXIT_NODES


class TORClassifierPlugin(EnrichmentPlugin):
    """
    Classifies the alert's ip_address against the TOR exit node list.

    Depends on GeoIPPlugin running first to set ip_address.
    Plugin order in the pipeline matters.
    """

    def enrich(self, alert: dict) -> dict:
        ip = alert.get("ip_address", "")
        alert["enrichment_type"] = "tor_exit_node" if ip in _MOCK_TOR_EXIT_NODES else "clean"
        return alert
