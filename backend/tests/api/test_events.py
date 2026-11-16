from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from modules.events import Event, EventCategory, EventDraft, TimeRange
from modules.sources import Source, SourceDraft, SourceUpdate


class StubEventRepository:
    def __init__(self, events: list[Event]) -> None:
        self._events = events
        self.was_called = False
        self.time_range: TimeRange | None = None
        self.limit: int | None = None
        self.categories: Sequence[EventCategory] = ()
        self.q: str | None = None
        self.offset = 0
        self.event_ids: Sequence[UUID] | None = None

    def upsert(self, draft: EventDraft) -> Event:
        raise NotImplementedError

    def list_upcoming(
        self,
        *,
        time_range: TimeRange,
        limit: int = 20,
        categories: Sequence[EventCategory] = (),
        q: str | None = None,
        offset: int = 0,
        event_ids: Sequence[UUID] | None = None,
    ) -> list[Event]:
        self.was_called = True
        self.time_range = time_range
        self.limit = limit
        self.categories = categories
        self.q = q
        self.offset = offset
        self.event_ids = event_ids
        return self._events


class StubSourceRepository:
    def __init__(self, source: Source) -> None:
        self._source = source

    def create(self, draft: SourceDraft) -> Source:
        raise NotImplementedError

    def get(self, source_id: UUID) -> Source | None:
        return self._source if source_id == self._source.id else None

    def get_by_base_url(self, base_url: str) -> Source | None:
        return self._source if base_url == self._source.base_url else None

    def update(self, source_id: UUID, changes: SourceUpdate) -> Source | None:
        raise NotImplementedError

    def list_enabled(self) -> list[Source]:
        raise NotImplementedError


def _event(source_id: UUID) -> Event:
    return Event(
        id=UUID("019a57c0-8800-7000-8000-000000000001"),
        title="Jazz Night",
        summary="Live jazz in the city centre.",
        category=EventCategory.MUSIC,
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
        {"from": "2026-11-01T00:00:00+00:00", "limit": 21},
        {"from": "2026-11-01T00:00:00Z", "offset": -1},
        {"from": "2026-11-01T00:00:00Z", "category": ["invalid"]},
        {"from": "2026-11-01T00:00:00Z", "to": "2026-11-02T00:00:00"},
        {"from": "2026-11-01T00:00:00Z", "to": "2026-11-01T02:00:00+02:00"},
        {"from": "2026-11-01T00:00:00Z", "to": "2026-10-31T00:00:00Z"},
    ),
)
def test_list_events_rejects_invalid_query_parameters(
    params: dict[str, str | int | list[str]],
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
        response = client.request("QUERY", "/api/events", json=params)

    assert response.status_code == 422
    assert not events.was_called


@pytest.mark.parametrize("limit", (None, 1, 20))
def test_list_events_accepts_default_and_boundary_limits(
    limit: int | None,
) -> None:
    source = Source(
        id=UUID("019a57c0-8800-7000-8000-000000000010"),
        name="Cultural Station",
        base_url="https://example.com",
        enabled=True,
    )
    events = StubEventRepository([])
    app = create_app(events, StubSourceRepository(source))

    params: dict[str, str | int] = {"from": "2026-11-01T00:00:00+00:00"}
    if limit is not None:
        params["limit"] = limit

    with TestClient(app) as client:
        response = client.request("QUERY", "/api/events", json=params)

    assert response.status_code == 200
    assert events.was_called
    assert events.limit == (20 if limit is None else limit)


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
        response = client.request(
            "QUERY",
            "/api/events",
            json={"from": "2026-11-01T00:00:00+00:00"},
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
        response = client.request(
            "QUERY",
            "/api/events",
            json={"from": "2026-11-01T00:00:00+00:00", "limit": 10},
        )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(event.id),
            "title": "Jazz Night",
            "summary": "Live jazz in the city centre.",
            "category": "music",
            "starts_at": "2026-11-05T19:00:00Z",
            "ends_at": None,
            "location_name": "Cultural Station",
            "source_name": "Cultural Station",
            "source_url": "https://example.com/events/jazz-night",
        }
    ]
    assert events.time_range == TimeRange(datetime(2026, 11, 1, tzinfo=UTC))
    assert events.limit == 10


def test_list_events_passes_filters_and_pagination_to_repository() -> None:
    source = Source(
        id=UUID(int=1),
        name="Source",
        base_url="https://example.com",
        enabled=True,
    )
    events = StubEventRepository([])
    with TestClient(create_app(events, StubSourceRepository(source))) as client:
        response = client.request(
            "QUERY",
            "/api/events",
            json={
                "from": "2026-11-01T02:00:00+02:00",
                "to": "2026-11-08T00:00:00Z",
                "category": ["music", "film"],
                "q": "PARTY",
                "offset": 3,
                "limit": 5,
            },
        )

    assert response.status_code == 200
    assert response.json() == []
    assert events.time_range == TimeRange(
        datetime(2026, 11, 1, tzinfo=UTC),
        datetime(2026, 11, 8, tzinfo=UTC),
    )
    assert events.categories == [EventCategory.MUSIC, EventCategory.FILM]
    assert events.q == "PARTY"
    assert events.offset == 3
    assert events.limit == 5


@pytest.mark.parametrize("id_filter", [{}, {"event_ids": None}])
def test_query_events_without_ids_browses_all_events(
    id_filter: dict[str, object],
) -> None:
    source = Source(
        id=UUID(int=1),
        name="Source",
        base_url="https://example.com",
        enabled=True,
    )
    event = _event(source.id)
    events = StubEventRepository([event])
    with TestClient(create_app(events, StubSourceRepository(source))) as client:
        response = client.request(
            "QUERY",
            "/api/events",
            json={"from": "2026-11-01T00:00:00Z"} | id_filter,
        )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(event.id)]
    assert events.was_called
    assert events.event_ids is None


def test_get_events_is_not_allowed() -> None:
    source = Source(
        id=UUID(int=1),
        name="Source",
        base_url="https://example.com",
        enabled=True,
    )
    events = StubEventRepository([])
    with TestClient(create_app(events, StubSourceRepository(source))) as client:
        response = client.get(
            "/api/events", params={"from": "2026-11-01T00:00:00Z"}
        )
    assert response.status_code == 405
    assert response.headers["allow"] == "QUERY"
    assert not events.was_called


def test_query_events_preserves_representation_with_selected_ids() -> None:
    source = Source(
        id=UUID(int=1),
        name="Source",
        base_url="https://example.com",
        enabled=True,
    )
    events = StubEventRepository([_event(source.id)])
    with TestClient(create_app(events, StubSourceRepository(source))) as client:
        expected = client.request(
            "QUERY", "/api/events", json={"from": "2026-11-01T00:00:00Z"}
        )
        response = client.request(
            "QUERY",
            "/api/events",
            json={
                "event_ids": [str(_event(source.id).id)],
                "from": "2026-11-01T00:00:00Z",
            },
        )

    assert response.status_code == 200
    assert expected.status_code == 200
    assert response.json() == expected.json()
    assert response.json()[0]["id"] == str(_event(source.id).id)


def test_query_events_passes_filters_and_pagination_to_repository() -> None:
    source = Source(
        id=UUID(int=1),
        name="Source",
        base_url="https://example.com",
        enabled=True,
    )
    events = StubEventRepository([])
    with TestClient(create_app(events, StubSourceRepository(source))) as client:
        response = client.request(
            "QUERY",
            "/api/events",
            json={
                "event_ids": [str(UUID(int=2))],
                "from": "2026-11-01T02:00:00+02:00",
                "to": "2026-11-08T00:00:00Z",
                "category": ["music", "film"],
                "q": "PARTY",
                "limit": 5,
                "offset": 3,
            },
        )
    assert response.status_code == 200
    assert events.event_ids == [UUID(int=2)]
    assert events.time_range == TimeRange(
        datetime(2026, 11, 1, tzinfo=UTC), datetime(2026, 11, 8, tzinfo=UTC)
    )
    assert events.categories == [EventCategory.MUSIC, EventCategory.FILM]
    assert events.q == "PARTY"
    assert events.limit == 5
    assert events.offset == 3


INVALID_QUERY_FIELDS: list[dict[str, object]] = [
    {"event_ids": ["invalid"]},
    {"event_ids": "invalid"},
    {"from": "2026-11-01T00:00:00"},
    {"to": "2026-11-02T00:00:00"},
    {"to": "2026-11-01T00:00:00Z"},
    {"to": "2026-10-31T00:00:00Z"},
    {"category": ["invalid"]},
    {"category": "music"},
    {"limit": 0},
    {"limit": 21},
    {"offset": -1},
]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"event_ids": []},
        *[
            {"event_ids": [], "from": "2026-11-01T00:00:00Z"} | invalid
            for invalid in INVALID_QUERY_FIELDS
        ],
    ],
)
def test_query_events_rejects_invalid_body(body: dict[str, object]) -> None:
    source = Source(
        id=UUID(int=1),
        name="Source",
        base_url="https://example.com",
        enabled=True,
    )
    events = StubEventRepository([])
    with TestClient(create_app(events, StubSourceRepository(source))) as client:
        response = client.request("QUERY", "/api/events", json=body)
    assert response.status_code == 422
    assert not events.was_called


@pytest.mark.parametrize(
    ("content", "content_type"),
    [
        (None, None),
        ("{", "application/json"),
        ('{"event_ids":[],"from":"2026-11-01T00:00:00Z"}', None),
        ('{"event_ids":[],"from":"2026-11-01T00:00:00Z"}', "text/plain"),
    ],
)
def test_query_events_requires_json_content_type_and_valid_body(
    content: str | None, content_type: str | None
) -> None:
    source = Source(
        id=UUID(int=1),
        name="Source",
        base_url="https://example.com",
        enabled=True,
    )
    events = StubEventRepository([])
    with TestClient(create_app(events, StubSourceRepository(source))) as client:
        response = client.request(
            "QUERY",
            "/api/events",
            content=content,
            headers={"Content-Type": content_type} if content_type else {},
        )
    assert response.status_code == 422
    assert not events.was_called


@pytest.mark.parametrize("limit", [None, 1, 20])
def test_query_events_accepts_page_boundaries_and_empty_ids(
    limit: int | None,
) -> None:
    source = Source(
        id=UUID(int=1),
        name="Source",
        base_url="https://example.com",
        enabled=True,
    )
    events = StubEventRepository([])
    body: dict[str, object] = {"event_ids": [], "from": "2026-11-01T00:00:00Z"}
    if limit is not None:
        body["limit"] = limit
    with TestClient(create_app(events, StubSourceRepository(source))) as client:
        response = client.request("QUERY", "/api/events", json=body)
    assert response.status_code == 200
    assert response.json() == []
    assert events.event_ids == []
    assert events.limit == (20 if limit is None else limit)
    assert events.offset == 0
