"""Public application interface for the Sources module."""

from typing import Protocol
from uuid import UUID

from modules.sources.contracts import SourceDraft, SourceUpdate
from modules.sources.domain import Source


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
