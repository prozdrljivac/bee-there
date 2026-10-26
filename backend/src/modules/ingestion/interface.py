"""Public interfaces for the Ingestion module."""

from typing import Protocol

from modules.ingestion.contracts import ExtractedEvent
from modules.sources import CandidateListing


class EventExtractor(Protocol):
    """Convert candidate content into canonical event fields."""

    def extract(self, candidate: CandidateListing) -> ExtractedEvent:
        """Extract one candidate listing."""
        ...
