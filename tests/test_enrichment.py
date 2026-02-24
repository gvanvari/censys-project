"""
Tests for the enrichment plugins.

Focus: plugin output validity and plugin interface contract.
"""

from enrichment.geo_ip import GeoIPPlugin, _random_public_ip
from enrichment.tor_classifier import _MOCK_TOR_EXIT_NODES, TORClassifierPlugin


class TestGeoIPPlugin:
    def test_adds_ip_address_field(self):
        plugin = GeoIPPlugin()
        alert = {"source": "splunk-prod", "severity": "high"}
        result = plugin.enrich(alert)
        assert "ip_address" in result

    def test_ip_is_valid_format(self):
        plugin = GeoIPPlugin()
        alert = {}
        result = plugin.enrich(alert)
        parts = result["ip_address"].split(".")
        assert len(parts) == 4
        assert all(0 <= int(p) <= 255 for p in parts)

    def test_ip_is_not_private_rfc1918(self):
        # Run many times to statistically verify no private IPs slip through
        private_prefixes = ("10.", "192.168.", "172.16.", "127.", "169.254.")
        for _ in range(200):
            ip = _random_public_ip()
            assert not any(ip.startswith(p) for p in private_prefixes), f"Got private IP: {ip}"

    def test_does_not_remove_existing_fields(self):
        plugin = GeoIPPlugin()
        alert = {"source": "splunk-prod", "severity": "critical", "description": "test"}
        result = plugin.enrich(alert)
        assert result["source"] == "splunk-prod"
        assert result["severity"] == "critical"
        assert result["description"] == "test"


class TestTORClassifierPlugin:
    def test_classifies_known_tor_ip(self):
        plugin = TORClassifierPlugin()
        tor_ip = next(iter(_MOCK_TOR_EXIT_NODES))
        alert = {"ip_address": tor_ip}
        result = plugin.enrich(alert)
        assert result["enrichment_type"] == "tor_exit_node"

    def test_classifies_clean_ip(self):
        plugin = TORClassifierPlugin()
        alert = {"ip_address": "8.8.8.8"}  # Not in TOR list
        result = plugin.enrich(alert)
        assert result["enrichment_type"] == "clean"

    def test_handles_missing_ip(self):
        plugin = TORClassifierPlugin()
        alert = {}
        result = plugin.enrich(alert)
        # Should default to "clean" when ip_address is absent
        assert result["enrichment_type"] == "clean"

    def test_enrichment_type_is_valid_enum_value(self):
        plugin = TORClassifierPlugin()
        alert = {"ip_address": "1.2.3.4"}
        result = plugin.enrich(alert)
        assert result["enrichment_type"] in ("tor_exit_node", "clean")
