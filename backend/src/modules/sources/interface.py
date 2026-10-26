"""Public application interface for the Sources module."""

from typing import Protocol
from uuid import UUID

from modules.sources.contracts import (
    CandidateListing,
    SourceDraft,
    SourceUpdate,
)
from modules.sources.domain import Source


class SourceAdapter(Protocol):
    """Retrieve candidate event listings from one source."""

    def fetch_candidates(self, source: Source) -> list[CandidateListing]:
        """Fetch candidate listings from a source."""
        ...


class SourceRepository(Protocol):
    """Persistence operations exposed by the Sources module."""

    def create(self, draft: SourceDraft) -> Source:
        """Create an event source."""
        ...

    def get(self, source_id: UUID) -> Source | None:
        """Return one source by ID."""
        ...

    def update(self, source_id: UUID, changes: SourceUpdate) -> Source | None:
        """Update one source if it exists."""
        ...

    def list_enabled(self) -> list[Source]:
        """List enabled sources."""
        ...
