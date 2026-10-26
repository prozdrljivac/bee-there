"""Domain types owned by the Events module."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class EventCategory(StrEnum):
    """Stable primary categories for canonical events."""

    THEATRE = "theatre"
    MUSIC = "music"
    COMEDY = "comedy"
    FILM = "film"
    EXHIBITION = "exhibition"
    FESTIVAL = "festival"
    SPORTS = "sports"
    COMMUNITY = "community"
    LITERATURE = "literature"
    FAIR = "fair"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class Event:
    """A canonical event stored by the Events module."""

    id: UUID
    title: str
    summary: str
    category: EventCategory
    starts_at: datetime
    ends_at: datetime | None
    location_name: str | None
    source_id: UUID
    source_url: str
    external_id: str | None
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
