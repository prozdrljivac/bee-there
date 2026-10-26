"""Contracts owned by the Ingestion module."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    StringConstraints,
    model_validator,
)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(UTC)


RequiredText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]
OptionalText = (
    Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    | None
)
UtcDateTime = Annotated[datetime, AfterValidator(_to_utc)]


class ExtractedEvent(BaseModel):
    """Event fields extracted from one candidate listing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: RequiredText
    summary: RequiredText
    starts_at: UtcDateTime
    ends_at: UtcDateTime | None = None
    location_name: OptionalText = None

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        """Require an event to end after it starts."""
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("end time must be after start time")
        return self


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Summary of one source ingestion run."""

    discovered_count: int
    stored_count: int
    failed_count: int
