"""FastAPI application factory."""

from typing import Annotated

from fastapi import Body, FastAPI, HTTPException

from api.schemas import (
    ErrorResponse,
    EventQuery,
    EventResponse,
    QueryValidationError,
)
from modules.events import Event, EventRepository, TimeRange
from modules.sources import SourceRepository


def create_app(
    event_repository: EventRepository,
    source_repository: SourceRepository,
) -> FastAPI:
    """Create the BeeThere HTTP application."""
    app = FastAPI(
        title="BeeThere",
        redoc_url=None,
        swagger_ui_parameters={
            "supportedSubmitMethods": [
                "get",
                "put",
                "post",
                "delete",
                "options",
                "head",
                "patch",
                "trace",
                "query",
            ],
        },
    )
    app.openapi_version = "3.2.0"

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Report process health without database or network access.

        Returns {"status": "ok"} when the application can respond. This does not
        verify migrations, database readiness, or external services.
        """
        return {"status": "ok"}

    @app.api_route(
        "/api/events",
        methods=["QUERY"],
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
                    "Invalid JSON bodies, Content-Type, or fields return issues. "
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
                                            "loc": ["body", "from"],
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
        openapi_extra={
            # FastAPI does not yet include QUERY in METHODS_WITH_BODY.
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/EventQuery"},
                    },
                },
            },
        },
    )
    def query_events(
        body: Annotated[EventQuery, Body()],
    ) -> list[EventResponse]:
        """Search events that overlap the requested time window.

        All filters apply before pagination. Results are ordered by starts_at,
        then id. Returns a JSON array without a count or snapshot.
        Omitted or null IDs allow normal browsing without an ID restriction.
        Empty IDs match none; unknown IDs are ignored and duplicates match once.
        Requires a JSON body and Content-Type: application/json.
        """
        try:
            time_range = TimeRange(
                from_time=body.from_time, to_time=body.to_time
            )
        except ValueError as error:
            raise HTTPException(
                status_code=422, detail="to must be after from"
            ) from error
        events = event_repository.list_upcoming(
            time_range=time_range,
            limit=body.limit,
            categories=body.category or (),
            q=body.q,
            offset=body.offset,
            event_ids=body.event_ids,
        )
        return [to_event_response(event) for event in events]

    def to_event_response(event: Event) -> EventResponse:
        source = source_repository.get(event.source_id)
        if source is None:
            raise HTTPException(
                status_code=500,
                detail="event source is not configured",
            )
        return EventResponse(
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

    return app
