"""
Abstract base class for all enrichment plugins.

Why a base class:
  Adding a new enrichment source = new file implementing enrich().
  The pipeline calls plugins without knowing their internals — Strategy pattern.
"""

from abc import ABC, abstractmethod


class EnrichmentPlugin(ABC):
    @abstractmethod
    def enrich(self, alert: dict) -> dict:
        """
        Accepts a raw alert dict, returns the same dict with added fields.
        Must not remove or mutate existing fields.
        """
