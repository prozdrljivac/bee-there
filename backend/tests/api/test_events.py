from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from modules.events import Event, EventDraft
from modules.sources import Source, SourceDraft, SourceUpdate


class StubEventRepository:
    def __init__(self, events: list[Event]) -> None:
        self._events = events
        self.from_time: datetime | None = None
        self.limit: int | None = None

    def upsert(self, draft: EventDraft) -> Event:
        raise NotImplementedError

    def list_upcoming(self, *, from_time: datetime, limit: int) -> list[Event]:
        self.from_time = from_time
        self.limit = limit
        return self._events


class StubSourceRepository:
    def __init__(self, source: Source) -> None:
        self._source = source

    def create(self, draft: SourceDraft) -> Source:
        raise NotImplementedError

    def get(self, source_id: UUID) -> Source | None:
        return self._source if source_id == self._source.id else None

    def update(self, source_id: UUID, changes: SourceUpdate) -> Source | None:
        raise NotImplementedError

    def list_enabled(self) -> list[Source]:
        raise NotImplementedError


def _event(source_id: UUID) -> Event:
    return Event(
        id=UUID("019a57c0-8800-7000-8000-000000000001"),
        title="Jazz Night",
        summary="Live jazz in the city centre.",
        starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
        ends_at=None,
        location_name="Cultural Station",
        source_id=source_id,
        source_url="https://example.com/events/jazz-night",
        external_id="jazz-2026",
        last_seen_at=datetime(2026, 10, 23, 18, 0, tzinfo=UTC),
        created_at=datetime(2026, 10, 23, 18, 0, tzinfo=UTC),
        updated_at=datetime(2026, 10, 23, 18, 0, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    "params",
    (
        {},
        {"from": "2026-11-01T00:00:00"},
        {"from": "2026-11-01T00:00:00+00:00", "limit": 0},
        {"from": "2026-11-01T00:00:00+00:00", "limit": 101},
    ),
)
def test_list_events_rejects_invalid_query_parameters(
    params: dict[str, str | int],
) -> None:
    source = Source(
        id=UUID("019a57c0-8800-7000-8000-000000000010"),
        name="Cultural Station",
        base_url="https://example.com",
        enabled=True,
    )
    events = StubEventRepository([])
    app = create_app(events, StubSourceRepository(source))

    with TestClient(app) as client:
        response = client.get("/api/events", params=params)

    assert response.status_code == 422
    assert events.from_time is None


def test_list_events_uses_the_default_limit() -> None:
    source = Source(
        id=UUID("019a57c0-8800-7000-8000-000000000010"),
        name="Cultural Station",
        base_url="https://example.com",
        enabled=True,
    )
    events = StubEventRepository([])
    app = create_app(events, StubSourceRepository(source))

    with TestClient(app) as client:
        response = client.get(
            "/api/events",
            params={"from": "2026-11-01T00:00:00+00:00"},
        )

    assert response.status_code == 200
    assert events.limit == 20


def test_list_events_reports_an_event_without_a_configured_source() -> None:
    source = Source(
        id=UUID("019a57c0-8800-7000-8000-000000000010"),
        name="Cultural Station",
        base_url="https://example.com",
        enabled=True,
    )
    events = StubEventRepository([_event(UUID(int=0))])
    app = create_app(events, StubSourceRepository(source))

    with TestClient(app) as client:
        response = client.get(
            "/api/events",
            params={"from": "2026-11-01T00:00:00+00:00"},
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "event source is not configured"}


def test_list_events_returns_upcoming_events_with_source_names() -> None:
    source = Source(
        id=UUID("019a57c0-8800-7000-8000-000000000010"),
        name="Cultural Station",
        base_url="https://example.com",
        enabled=True,
    )
    event = _event(source.id)
    events = StubEventRepository([event])
    app = create_app(events, StubSourceRepository(source))

    with TestClient(app) as client:
        response = client.get(
            "/api/events",
            params={"from": "2026-11-01T00:00:00+00:00", "limit": 10},
        )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(event.id),
            "title": "Jazz Night",
            "summary": "Live jazz in the city centre.",
            "starts_at": "2026-11-05T19:00:00Z",
            "ends_at": None,
            "location_name": "Cultural Station",
            "source_name": "Cultural Station",
            "source_url": "https://example.com/events/jazz-night",
        }
    ]
    assert events.from_time == datetime(2026, 11, 1, tzinfo=UTC)
    assert events.limit == 10
