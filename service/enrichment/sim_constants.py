"""
Shared simulation constants for enrichment plugins.

MOCK_TOR_EXIT_NODES simulates a cached copy of the Tor Project's bulk exit
node list (https://check.torproject.org/torbulkexitlist).

This set is referenced by:
  - geo_ip.py  — occasionally assigns one of these IPs so the pipeline
                 produces realistic TOR-flagged alerts
  - tor_classifier.py — looks up the alert IP against this set
"""

MOCK_TOR_EXIT_NODES: frozenset = frozenset(
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

# Sorted list used for O(1) random.choice lookups
_TOR_IP_LIST: list = sorted(MOCK_TOR_EXIT_NODES)
