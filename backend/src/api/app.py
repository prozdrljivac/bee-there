"""FastAPI application factory."""

from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from pydantic import AwareDatetime

from api.schemas import ErrorResponse, EventResponse, QueryValidationError
from modules.events import EventCategory, EventRepository, TimeRange
from modules.sources import SourceRepository


def create_app(
    event_repository: EventRepository,
    source_repository: SourceRepository,
) -> FastAPI:
    """Create the BeeThere HTTP application."""
    app = FastAPI(title="BeeThere")

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Report process health without database or network access.

        Returns {"status": "ok"} when the application can respond. This does not
        verify migrations, database readiness, or external services.
        """
        return {"status": "ok"}

    @app.get(
        "/api/events",
        response_model=list[EventResponse],
        responses={
            200: {
                "description": (
                    "Matching events in chronological order. Returns an empty "
                    "array when no matches remain at the requested offset."
                ),
            },
            422: {
                "model": QueryValidationError | ErrorResponse,
                "description": (
                    "Invalid or missing query values return a list of issues. "
                    "A to bound at or before from returns a string reason."
                ),
                "content": {
                    "application/json": {
                        "examples": {
                            "invalid_query": {
                                "summary": "Missing required from bound",
                                "value": {
                                    "detail": [
                                        {
                                            "loc": ["query", "from"],
                                            "msg": "Field required",
                                            "type": "missing",
                                        }
                                    ]
                                },
                            },
                            "invalid_range": {
                                "summary": "Upper bound must follow lower bound",
                                "value": {"detail": "to must be after from"},
                            },
                        },
                    },
                },
            },
            500: {
                "model": ErrorResponse,
                "description": "An event refers to an unconfigured source.",
                "content": {
                    "application/json": {
                        "examples": {
                            "missing_source": {
                                "value": {
                                    "detail": "event source is not configured",
                                },
                            },
                        },
                    },
                },
            },
        },
    )
    def list_events(
        from_time: Annotated[
            AwareDatetime,
            Query(
                alias="from",
                description=(
                    "Required lower bound with a timezone (Z or UTC offset). "
                    "Includes ongoing events whose end is after this bound. "
                    "Events with no end must start at or after this bound."
                ),
                examples=["2026-11-01T00:00:00Z"],
            ),
        ],
        limit: Annotated[
            int,
            Query(ge=1, le=20, description="Maximum events per page."),
        ] = 20,
        to_time: Annotated[
            AwareDatetime | None,
            Query(
                alias="to",
                description=(
                    "Optional exclusive upper bound on event start time. "
                    "Must include a timezone and be after from. "
                    "Omit for no upper bound."
                ),
                examples=["2026-11-08T00:00:00Z"],
            ),
        ] = None,
        category: Annotated[
            list[EventCategory] | None,
            Query(
                description=(
                    "Repeat category to match any selected value, for example "
                    "category=music&category=film. Omit to include all categories."
                ),
            ),
        ] = None,
        q: Annotated[
            str | None,
            Query(
                description=(
                    "Literal, case-insensitive substring search in the title "
                    "using Unicode case folding. Spaces are not trimmed. "
                    "Omit or use an empty string for no search."
                ),
                examples=["jazz"],
            ),
        ] = None,
        offset: Annotated[
            int,
            Query(
                ge=0,
                description=(
                    "Number of matching events to skip after filtering and "
                    "ordering. Increase by limit to request the next page."
                ),
            ),
        ] = 0,
    ) -> list[EventResponse]:
        """List events that overlap the requested time window.

        Filters are combined: time window, any selected category, and title search.
        Results are ordered by starts_at ascending, then id ascending for ties.
        Pagination is applied after all filters. Returns a JSON array, with no
        total count or page envelope. An empty array means no matching events
        remain at this offset.
        """
        try:
            time_range = TimeRange(from_time=from_time, to_time=to_time)
        except ValueError as error:
            raise HTTPException(
                status_code=422, detail="to must be after from"
            ) from error
        events = event_repository.list_upcoming(
            time_range=time_range,
            limit=limit,
            categories=category or (),
            q=q,
            offset=offset,
        )
        response: list[EventResponse] = []
        for event in events:
            source = source_repository.get(event.source_id)
            if source is None:
                raise HTTPException(
                    status_code=500,
                    detail="event source is not configured",
                )
            response.append(
                EventResponse(
                    id=event.id,
                    title=event.title,
                    summary=event.summary,
                    category=event.category,
                    starts_at=event.starts_at,
                    ends_at=event.ends_at,
                    location_name=event.location_name,
                    source_name=source.name,
                    source_url=event.source_url,
                )
            )
        return response

    return app
