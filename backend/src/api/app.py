"""FastAPI application factory."""

from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from pydantic import AwareDatetime

from api.schemas import EventResponse
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
        """Report process health without database or network access."""
        return {"status": "ok"}

    @app.get("/api/events", response_model=list[EventResponse])
    def list_events(
        from_time: Annotated[AwareDatetime, Query(alias="from")],
        limit: Annotated[int, Query(ge=1, le=20)] = 20,
        to_time: Annotated[AwareDatetime | None, Query(alias="to")] = None,
        category: Annotated[list[EventCategory] | None, Query()] = None,
        q: str | None = None,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[EventResponse]:
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
