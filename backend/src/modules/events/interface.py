"""Public application interface for the Events module."""

from collections.abc import Sequence
from typing import Protocol

from modules.events.contracts import EventDraft, TimeRange
from modules.events.domain import Event, EventCategory


class EventRepository(Protocol):
    """Persistence operations exposed by the Events module."""

    def upsert(self, draft: EventDraft) -> Event:
        """Insert or update an event from one source listing."""
        ...

    def list_upcoming(
        self,
        *,
        time_range: TimeRange,
        limit: int = 20,
        categories: Sequence[EventCategory] = (),
        q: str | None = None,
        offset: int = 0,
    ) -> list[Event]:
        """List overlapping events with optional filters and stable pagination."""
        ...
