"""HTTP request and response schemas."""

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field

from modules.events import EventCategory


class EventQuery(BaseModel):
    """Search events within a required time window, optionally by ID."""

    event_ids: list[UUID] | None = Field(
        default=None,
        description=(
            "Selected IDs. Omit or use null for all IDs; an empty array matches none. "
            "Unknown and repeated IDs are ignored."
        ),
    )
    from_time: AwareDatetime = Field(
        alias="from",
        description=(
            "Required lower bound with a timezone (Z or UTC offset). "
            "Includes ongoing events whose end is after this bound. "
            "Events with no end must start at or after this bound."
        ),
        examples=["2026-11-01T00:00:00Z"],
    )
    to_time: AwareDatetime | None = Field(
        default=None,
        alias="to",
        description=(
            "Optional exclusive upper bound on event start time. "
            "Must include a timezone and be after from. Omit or use null for no upper bound."
        ),
        examples=["2026-11-08T00:00:00Z"],
    )
    category: list[EventCategory] | None = Field(
        default=None,
        description=(
            "Array of categories to match, for example [music, film]. "
            "Omit, use null, or use an empty array for all categories."
        ),
    )
    q: str | None = Field(
        default=None,
        description=(
            "Literal, case-insensitive substring search in the title using Unicode "
            "case folding. Spaces are not trimmed. Omit, use null, or use an empty "
            "string for no search."
        ),
        examples=["jazz"],
    )
    limit: int = Field(
        default=20, ge=1, le=20, description="Maximum events per page."
    )
    offset: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of matching events to skip after filtering and ordering. "
            "Increase by limit to request the next page."
        ),
    )


class EventResponse(BaseModel):
    """Public representation of an upcoming event."""

    id: UUID = Field(description="Stable event identifier.")
    title: str = Field(description="Event title.")
    summary: str = Field(description="Short event description.")
    category: EventCategory = Field(description="Event category.")
    starts_at: AwareDatetime = Field(description="Start time with a timezone.")
    ends_at: AwareDatetime | None = Field(
        description="End time with a timezone, or null when unknown."
    )
    location_name: str | None = Field(
        description="Venue or location name, or null when unknown."
    )
    source_name: str = Field(description="Name of the event's source.")
    source_url: str = Field(description="Original event listing URL.")


class ErrorResponse(BaseModel):
    """Application error with a readable reason."""

    detail: str = Field(
        description="Reason the request could not be completed."
    )


class QueryValidationIssue(BaseModel):
    """Request validation issue reported by FastAPI."""

    loc: list[str | int] = Field(description="Location of the invalid value.")
    msg: str = Field(description="Explanation of the validation failure.")
    type: str = Field(description="Validation error code.")


class QueryValidationError(BaseModel):
    """Invalid or missing request values; issues can include extra context."""

    detail: list[QueryValidationIssue]
