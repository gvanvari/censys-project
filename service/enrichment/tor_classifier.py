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

# Simulates a cached TOR exit node list fetched from check.torproject.org
_MOCK_TOR_EXIT_NODES: frozenset = frozenset(
    {
        "185.220.101.35",
        "185.220.101.47",
        "104.244.72.115",
        "199.87.154.255",
        "162.247.74.27",
        "176.10.104.240",
        "51.15.43.205",
        "45.33.32.156",
        "23.129.64.131",
        "204.13.164.118",
        "171.25.193.77",
        "94.230.208.147",
        "77.247.181.163",
        "193.11.114.43",
        "37.187.129.166",
        "217.170.205.14",
        "80.67.172.162",
        "195.176.3.19",
        "109.70.100.28",
        "46.165.230.5",
    }
)


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
