"""Public interface for the Events module."""

from infrastructure.persistence import (
    PersistenceConflictError,
    PersistenceError,
)
from modules.events.contracts import EventDraft
from modules.events.domain import Event
from modules.events.interface import EventRepository

__all__ = [
    "Event",
    "EventDraft",
    "EventRepository",
    "PersistenceConflictError",
    "PersistenceError",
]
