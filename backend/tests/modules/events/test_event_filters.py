from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from infrastructure.migrations import upgrade_database
from modules.events import EventCategory, EventDraft, TimeRange
from modules.events.sqlite import SQLiteEventRepository
from modules.sources import SourceDraft
from modules.sources.sqlite import SQLiteSourceRepository


def at(day: int) -> datetime:
    return datetime(2026, 11, day, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path: Path) -> SQLiteEventRepository:
    path = tmp_path / "events.sqlite3"
    upgrade_database(path)
    return SQLiteEventRepository(path)


def add_event(
    repository: SQLiteEventRepository,
    tmp_path: Path,
    *,
    title: str = "Jazz Night",
    starts_at: datetime = datetime(2026, 11, 5, tzinfo=UTC),
    ends_at: datetime | None = None,
    category: EventCategory = EventCategory.MUSIC,
) -> None:
    source = SQLiteSourceRepository(tmp_path / "events.sqlite3").create(
        SourceDraft(
            name=f"Source {uuid4()}", base_url=f"https://example.com/{uuid4()}"
        )
    )
    repository.upsert(
        EventDraft(
            title=title,
            summary="An event.",
            starts_at=starts_at,
            ends_at=ends_at,
            category=category,
            source_id=source.id,
            source_url=f"https://example.com/events/{uuid4()}",
        )
    )


def test_includes_ongoing_events_but_not_events_ending_at_from(
    repository: SQLiteEventRepository, tmp_path: Path
) -> None:
    add_event(
        repository, tmp_path, title="Ongoing", starts_at=at(1), ends_at=at(6)
    )
    add_event(
        repository, tmp_path, title="Ended", starts_at=at(1), ends_at=at(5)
    )
    add_event(repository, tmp_path, title="Past", starts_at=at(4))
    add_event(repository, tmp_path, title="At lower bound")

    events = repository.list_upcoming(time_range=TimeRange(at(5)), limit=20)

    assert [event.title for event in events] == ["Ongoing", "At lower bound"]


def test_upper_bound_excludes_starts_at_to(
    repository: SQLiteEventRepository, tmp_path: Path
) -> None:
    add_event(
        repository, tmp_path, title="Ongoing", starts_at=at(1), ends_at=at(9)
    )
    add_event(repository, tmp_path, title="Inside", starts_at=at(6))
    add_event(repository, tmp_path, title="At upper bound", starts_at=at(7))
    add_event(
        repository, tmp_path, title="Later", starts_at=at(8), ends_at=at(9)
    )

    events = repository.list_upcoming(
        time_range=TimeRange(at(5), at(7)), limit=20
    )

    assert [event.title for event in events] == ["Ongoing", "Inside"]


def test_title_search_uses_unicode_casefold_without_removing_accents(
    repository: SQLiteEventRepository, tmp_path: Path
) -> None:
    for title in ("Other", "CAFÉ tonight", "café later", "Cafe", "Coffee"):
        add_event(repository, tmp_path, title=title)
    add_event(repository, tmp_path, title="café past", starts_at=at(1))
    add_event(repository, tmp_path, title="café future", starts_at=at(9))

    events = repository.list_upcoming(
        time_range=TimeRange(at(5), at(7)), q="CaFÉ", limit=1
    )

    assert [event.title for event in events] == ["CAFÉ tonight"]
    assert [
        event.title
        for event in repository.list_upcoming(
            time_range=TimeRange(at(5), at(7)), q="CaFÉ"
        )
    ] == ["CAFÉ tonight", "café later"]


def test_categories_are_or_and_combine_with_title_and_dates(
    repository: SQLiteEventRepository, tmp_path: Path
) -> None:
    for category in (
        EventCategory.MUSIC,
        EventCategory.FILM,
        EventCategory.OTHER,
    ):
        add_event(
            repository, tmp_path, title=f"Night {category}", category=category
        )
    add_event(repository, tmp_path, title="Day", category=EventCategory.FILM)
    add_event(repository, tmp_path, title="Night past", starts_at=at(1))

    events = repository.list_upcoming(
        time_range=TimeRange(at(5)),
        categories=[EventCategory.MUSIC, EventCategory.FILM],
        q="night",
        limit=20,
    )

    assert [event.title for event in events] == ["Night music", "Night film"]


@pytest.mark.parametrize("q", [None, "night"])
def test_pagination_is_stable_and_applied_after_filters(
    repository: SQLiteEventRepository, tmp_path: Path, q: str | None
) -> None:
    ids = iter(UUID(int=value) for value in (4, 3, 2, 1))
    repository = SQLiteEventRepository(
        tmp_path / "events.sqlite3", id_factory=lambda: next(ids)
    )
    add_event(
        repository,
        tmp_path,
        title="Wrong category",
        category=EventCategory.FILM,
    )
    for title in ("Night first", "Night second", "Night third"):
        add_event(repository, tmp_path, title=title)
    expected = repository.list_upcoming(
        time_range=TimeRange(at(5)), categories=[EventCategory.MUSIC], q=q
    )
    page = repository.list_upcoming(
        time_range=TimeRange(at(5)),
        categories=[EventCategory.MUSIC],
        q=q,
        limit=1,
        offset=1,
    )

    assert page == expected[1:2]
    assert [(event.starts_at, event.id) for event in expected] == sorted(
        (event.starts_at, event.id) for event in expected
    )
    assert (
        repository.list_upcoming(time_range=TimeRange(at(5)), offset=100, q=q)
        == []
    )


@pytest.mark.parametrize(
    ("to_time", "limit", "offset"),
    [
        (at(5), 20, 0),
        (at(4), 20, 0),
        (datetime(2026, 11, 7), 20, 0),
        (None, 0, 0),
        (None, 20, -1),
    ],
)
def test_repository_rejects_invalid_interval_or_page(
    repository: SQLiteEventRepository,
    to_time: datetime | None,
    limit: int,
    offset: int,
) -> None:
    with pytest.raises(ValueError):
        repository.list_upcoming(
            time_range=TimeRange(at(5), to_time), limit=limit, offset=offset
        )


def test_api_filters_real_events_before_pagination(
    repository: SQLiteEventRepository, tmp_path: Path
) -> None:
    add_event(repository, tmp_path, title="Wrong title")
    add_event(
        repository,
        tmp_path,
        title="PARTY ongoing",
        starts_at=at(1),
        ends_at=at(6),
    )
    add_event(
        repository, tmp_path, title="party film", category=EventCategory.FILM
    )
    add_event(
        repository,
        tmp_path,
        title="party excluded",
        category=EventCategory.OTHER,
    )
    add_event(repository, tmp_path, title="party late", starts_at=at(9))
    app = create_app(
        repository, SQLiteSourceRepository(tmp_path / "events.sqlite3")
    )

    with TestClient(app) as client:
        response = client.request(
            "QUERY",
            "/api/events",
            json={
                "from": "2026-11-05T00:00:00Z",
                "to": "2026-11-07T00:00:00Z",
                "category": ["music", "film"],
                "q": "PaRtY",
                "offset": 1,
                "limit": 1,
            },
        )

    assert response.status_code == 200
    assert [event["title"] for event in response.json()] == ["party film"]


def test_id_filter_ignores_unknown_and_duplicate_ids(
    repository: SQLiteEventRepository, tmp_path: Path
) -> None:
    add_event(repository, tmp_path, title="Selected")
    add_event(repository, tmp_path, title="Not selected")
    selected = repository.list_upcoming(time_range=TimeRange(at(5)))[0]

    events = repository.list_upcoming(
        time_range=TimeRange(at(5)),
        event_ids=[selected.id, uuid4(), selected.id],
    )

    assert events == [selected]


@pytest.mark.parametrize("q", [None, "NIGHT"])
def test_query_ids_combine_with_filters_before_stable_pagination(
    repository: SQLiteEventRepository, tmp_path: Path, q: str | None
) -> None:
    ids = iter(UUID(int=value) for value in range(100, 0, -1))
    repository = SQLiteEventRepository(
        tmp_path / "events.sqlite3", id_factory=lambda: next(ids)
    )
    for index in range(45):
        add_event(repository, tmp_path, title=f"Night {index}")
    matching = repository.list_upcoming(time_range=TimeRange(at(5)), limit=100)
    for title, category, start, end in [
        ("Night past", EventCategory.MUSIC, at(1), at(5)),
        ("Night late", EventCategory.MUSIC, at(7), None),
        ("Night other", EventCategory.OTHER, at(5), None),
    ]:
        add_event(
            repository,
            tmp_path,
            title=title,
            category=category,
            starts_at=start,
            ends_at=end,
        )
    # Select excluded events too, so IDs alone cannot satisfy the query.
    all_events = repository.list_upcoming(
        time_range=TimeRange(at(1)), limit=100
    )
    event_ids = [str(event.id) for event in all_events]
    event_ids += [event_ids[0], str(uuid4())]
    add_event(
        repository,
        tmp_path,
        title="Night not selected",
        starts_at=at(4),
        ends_at=at(6),
    )
    app = create_app(
        repository, SQLiteSourceRepository(tmp_path / "events.sqlite3")
    )
    with TestClient(app) as client:
        actual: list[str] = []
        for offset in (0, 20, 40, 60):
            response = client.request(
                "QUERY",
                "/api/events",
                json={
                    "event_ids": event_ids,
                    "from": "2026-11-05T00:00:00Z",
                    "to": "2026-11-07T00:00:00Z",
                    "category": ["music", "film"],
                    "q": q,
                    "offset": offset,
                },
            )
            assert response.status_code == 200
            page = response.json()
            assert len(page) == len(matching[offset : offset + 20])
            actual.extend(event["id"] for event in page)
    assert actual == [str(event.id) for event in matching]


@pytest.mark.parametrize("event_ids", [[], [UUID(int=999)]])
def test_id_filter_matches_no_events_for_empty_or_unknown_ids(
    repository: SQLiteEventRepository, tmp_path: Path, event_ids: list[UUID]
) -> None:
    add_event(repository, tmp_path)
    assert (
        repository.list_upcoming(
            time_range=TimeRange(at(5)), event_ids=event_ids
        )
        == []
    )
