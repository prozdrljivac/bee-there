"""Public application interface for the Events module."""

from datetime import datetime
from typing import Protocol

from modules.events.contracts import EventDraft
from modules.events.domain import Event


class EventRepository(Protocol):
    """Persistence operations exposed by the Events module."""

    def upsert(self, draft: EventDraft) -> Event:
        """Insert or update an event from one source listing."""
        ...

    def list_upcoming(self, *, from_time: datetime, limit: int) -> list[Event]:
        """List events that start on or after the supplied time."""
        ...
