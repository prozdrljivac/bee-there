"""HTTP response schemas."""

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field

from modules.events import EventCategory


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
    """Invalid or missing query values; issues can include extra context."""

    detail: list[QueryValidationIssue]
