"""HTTP response schemas."""

from uuid import UUID

from pydantic import AwareDatetime, BaseModel


class EventResponse(BaseModel):
    """Public representation of an upcoming event."""

    id: UUID
    title: str
    summary: str
    starts_at: AwareDatetime
    ends_at: AwareDatetime | None
    location_name: str | None
    source_name: str
    source_url: str
