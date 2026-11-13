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
        response = client.get(
            "/api/events",
            params=[
                ("from", "2026-11-05T00:00:00Z"),
                ("to", "2026-11-07T00:00:00Z"),
                ("category", "music"),
                ("category", "film"),
                ("q", "PaRtY"),
                ("offset", "1"),
                ("limit", "1"),
            ],
        )

    assert response.status_code == 200
    assert [event["title"] for event in response.json()] == ["party film"]
