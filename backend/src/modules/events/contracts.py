"""Public input contracts for the Events module."""

from datetime import UTC, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    HttpUrl,
    StringConstraints,
    model_validator,
)

from modules.events.domain import EventCategory


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(UTC)


def _validate_source_url(value: str) -> str:
    return str(HttpUrl(value))


RequiredText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
OptionalText = (
    Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    | None
)
UtcDateTime = Annotated[datetime, AfterValidator(_to_utc)]
SourceUrl = Annotated[str, AfterValidator(_validate_source_url)]


class EventDraft(BaseModel):
    """Validated event data accepted by the Events module."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: RequiredText
    summary: RequiredText
    category: EventCategory
    starts_at: UtcDateTime
    ends_at: UtcDateTime | None = None
    location_name: OptionalText = None
    source_id: UUID
    source_url: SourceUrl
    external_id: OptionalText = None

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        """Require an event to end after it starts."""
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("end time must be after start time")
        return self
