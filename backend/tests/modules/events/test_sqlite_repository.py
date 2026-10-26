from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from infrastructure.migrations import upgrade_database
from modules.events import (
    EventDraft,
    PersistenceConflictError,
    PersistenceError,
)
from modules.events.sqlite import SQLiteEventRepository
from modules.sources import SourceDraft
from modules.sources.sqlite import SQLiteSourceRepository


@pytest.fixture(autouse=True)
def migrate_database(tmp_path: Path) -> None:
    upgrade_database(tmp_path / "events.sqlite3")


def _create_source(tmp_path: Path) -> UUID:
    source_id = uuid4()
    repository = SQLiteSourceRepository(
        tmp_path / "events.sqlite3",
        id_factory=lambda: source_id,
    )
    repository.create(
        SourceDraft(
            name=f"Source {source_id}",
            base_url=f"https://example.com/sources/{source_id}",
        )
    )
    return source_id


def test_upsert_raises_a_persistence_error_when_storage_fails(
    tmp_path: Path,
) -> None:
    repository = SQLiteEventRepository(tmp_path / "unmigrated.sqlite3")
    draft = EventDraft(
        title="Jazz Night",
        summary="Live jazz in the city centre.",
        starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
        source_id=uuid4(),
        source_url="https://example.com/events/jazz-night",
    )

    with pytest.raises(PersistenceError):
        repository.upsert(draft)


def test_upsert_rejects_an_unknown_source(tmp_path: Path) -> None:
    repository = SQLiteEventRepository(tmp_path / "events.sqlite3")
    draft = EventDraft(
        title="Jazz Night",
        summary="Live jazz in the city centre.",
        starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
        source_id=uuid4(),
        source_url="https://example.com/events/jazz-night",
    )

    with pytest.raises(PersistenceConflictError):
        repository.upsert(draft)


def test_upsert_stores_a_new_event(tmp_path: Path) -> None:
    event_id = UUID("019a57c0-8800-7000-8000-000000000001")
    now = datetime(2026, 10, 23, 18, 0, tzinfo=UTC)
    source_id = _create_source(tmp_path)
    repository = SQLiteEventRepository(
        tmp_path / "events.sqlite3",
        clock=lambda: now,
        id_factory=lambda: event_id,
    )
    draft = EventDraft(
        title="Jazz Night",
        summary="Live jazz in the city centre.",
        starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
        location_name="Cultural Station",
        source_id=source_id,
        source_url="https://example.com/events/jazz-night",
        external_id="jazz-2026",
    )

    event = repository.upsert(draft)

    assert event.id == event_id
    assert event.title == "Jazz Night"
    assert event.source_id == source_id
    assert event.source_url == "https://example.com/events/jazz-night"
    assert event.created_at == now
    assert event.updated_at == now
    assert event.last_seen_at == now


def test_upsert_updates_an_event_with_the_same_external_id(
    tmp_path: Path,
) -> None:
    event_id = UUID("019a57c0-8800-7000-8000-000000000001")
    first_seen = datetime(2026, 10, 23, 18, 0, tzinfo=UTC)
    seen_again = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)
    times = iter((first_seen, seen_again))
    repository = SQLiteEventRepository(
        tmp_path / "events.sqlite3",
        clock=lambda: next(times),
        id_factory=lambda: event_id,
    )
    source_id = _create_source(tmp_path)
    original = EventDraft(
        title="Jazz Night",
        summary="Initial summary.",
        starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
        source_id=source_id,
        source_url="https://example.com/events/jazz-night",
        external_id="jazz-2026",
    )
    revised = original.model_copy(
        update={"title": "Jazz Night: Revised", "summary": "Updated summary."}
    )
    created = repository.upsert(original)

    updated = repository.upsert(revised)

    assert updated.id == created.id
    assert updated.title == "Jazz Night: Revised"
    assert updated.summary == "Updated summary."
    assert updated.created_at == first_seen
    assert updated.updated_at == seen_again
    assert updated.last_seen_at == seen_again


def test_upsert_uses_the_source_url_when_no_external_id_exists(
    tmp_path: Path,
) -> None:
    event_id = UUID("019a57c0-8800-7000-8000-000000000001")
    times = iter(
        (
            datetime(2026, 10, 23, 18, 0, tzinfo=UTC),
            datetime(2026, 10, 24, 9, 0, tzinfo=UTC),
        )
    )
    database_path = tmp_path / "events.sqlite3"
    repository = SQLiteEventRepository(
        database_path,
        clock=lambda: next(times),
        id_factory=lambda: event_id,
    )
    draft = EventDraft(
        title="Jazz Night",
        summary="Initial summary.",
        starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
        source_id=_create_source(tmp_path),
        source_url="https://example.com/events/jazz-night",
    )
    created = repository.upsert(draft)

    updated = repository.upsert(
        draft.model_copy(update={"summary": "Updated summary."})
    )

    assert updated.id == created.id
    assert updated.summary == "Updated summary."


def test_upsert_scopes_external_ids_to_their_source(tmp_path: Path) -> None:
    now = datetime(2026, 10, 23, 18, 0, tzinfo=UTC)
    repository = SQLiteEventRepository(
        tmp_path / "events.sqlite3", clock=lambda: now
    )
    for title, source_id in (
        ("First", _create_source(tmp_path)),
        ("Second", _create_source(tmp_path)),
    ):
        repository.upsert(
            EventDraft(
                title=title,
                summary=f"Summary for {title}.",
                starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
                source_id=source_id,
                source_url=f"https://example.com/events/{title.lower()}",
                external_id="shared-external-id",
            )
        )

    events = repository.list_upcoming(from_time=now, limit=10)

    assert {event.title for event in events} == {"First", "Second"}


def test_upsert_keeps_a_known_external_id_when_a_listing_omits_it(
    tmp_path: Path,
) -> None:
    first_seen = datetime(2026, 10, 23, 18, 0, tzinfo=UTC)
    seen_again = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)
    times = iter((first_seen, seen_again))
    repository = SQLiteEventRepository(
        tmp_path / "events.sqlite3", clock=lambda: next(times)
    )
    draft = EventDraft(
        title="Jazz Night",
        summary="Live jazz in the city centre.",
        starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
        source_id=_create_source(tmp_path),
        source_url="https://example.com/events/jazz-night",
        external_id="jazz-2026",
    )
    created = repository.upsert(draft)

    updated = repository.upsert(draft.model_copy(update={"external_id": None}))

    events = repository.list_upcoming(from_time=first_seen, limit=10)
    assert updated.id == created.id
    assert updated.external_id == "jazz-2026"
    assert updated.updated_at == seen_again
    assert events == [updated]


def test_upsert_adds_an_external_id_to_an_existing_url_match(
    tmp_path: Path,
) -> None:
    event_id = UUID("019a57c0-8800-7000-8000-000000000001")
    now = datetime(2026, 10, 23, 18, 0, tzinfo=UTC)
    repository = SQLiteEventRepository(
        tmp_path / "events.sqlite3",
        clock=lambda: now,
        id_factory=lambda: event_id,
    )
    draft = EventDraft(
        title="Jazz Night",
        summary="Live jazz in the city centre.",
        starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
        source_id=_create_source(tmp_path),
        source_url="https://example.com/events/jazz-night",
    )
    created = repository.upsert(draft)

    updated = repository.upsert(
        draft.model_copy(update={"external_id": "jazz-2026"})
    )

    events = repository.list_upcoming(from_time=now, limit=10)
    assert updated.id == created.id
    assert updated.external_id == "jazz-2026"
    assert events == [updated]


def test_list_upcoming_raises_a_persistence_error_when_storage_fails(
    tmp_path: Path,
) -> None:
    repository = SQLiteEventRepository(tmp_path / "unmigrated.sqlite3")

    with pytest.raises(PersistenceError):
        repository.list_upcoming(
            from_time=datetime(2026, 10, 23, 18, 0, tzinfo=UTC),
            limit=10,
        )


def test_list_upcoming_returns_future_events_in_start_order(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 10, 23, 18, 0, tzinfo=UTC)
    repository = SQLiteEventRepository(
        tmp_path / "events.sqlite3", clock=lambda: now
    )
    source_id = _create_source(tmp_path)
    for title, starts_at in (
        ("Past", datetime(2026, 10, 22, 19, 0, tzinfo=UTC)),
        ("Later", datetime(2026, 10, 25, 19, 0, tzinfo=UTC)),
        ("Sooner", datetime(2026, 10, 24, 19, 0, tzinfo=UTC)),
    ):
        repository.upsert(
            EventDraft(
                title=title,
                summary=f"Summary for {title}.",
                starts_at=starts_at,
                source_id=source_id,
                source_url=f"https://example.com/events/{title.lower()}",
            )
        )

    events = repository.list_upcoming(from_time=now, limit=10)

    assert [event.title for event in events] == ["Sooner", "Later"]


def test_list_upcoming_includes_an_event_at_the_boundary(
    tmp_path: Path,
) -> None:
    boundary = datetime(2026, 10, 23, 18, 0, tzinfo=UTC)
    repository = SQLiteEventRepository(
        tmp_path / "events.sqlite3", clock=lambda: boundary
    )
    created = repository.upsert(
        EventDraft(
            title="Starting now",
            summary="An event at the requested boundary.",
            starts_at=boundary,
            source_id=_create_source(tmp_path),
            source_url="https://example.com/events/starting-now",
        )
    )

    assert repository.list_upcoming(from_time=boundary, limit=10) == [created]


def test_list_upcoming_applies_the_requested_limit(tmp_path: Path) -> None:
    now = datetime(2026, 10, 23, 18, 0, tzinfo=UTC)
    repository = SQLiteEventRepository(
        tmp_path / "events.sqlite3", clock=lambda: now
    )
    source_id = _create_source(tmp_path)
    for day in (24, 25):
        repository.upsert(
            EventDraft(
                title=f"Event on day {day}",
                summary="An upcoming event.",
                starts_at=datetime(2026, 10, day, 19, 0, tzinfo=UTC),
                source_id=source_id,
                source_url=f"https://example.com/events/{day}",
            )
        )

    events = repository.list_upcoming(from_time=now, limit=1)

    assert [event.title for event in events] == ["Event on day 24"]


def test_events_remain_available_after_the_database_is_reopened(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 10, 23, 18, 0, tzinfo=UTC)
    database_path = tmp_path / "events.sqlite3"
    repository = SQLiteEventRepository(database_path, clock=lambda: now)
    created = repository.upsert(
        EventDraft(
            title="Jazz Night",
            summary="Live jazz in the city centre.",
            starts_at=datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
            source_id=_create_source(tmp_path),
            source_url="https://example.com/events/jazz-night",
        )
    )

    reopened_repository = SQLiteEventRepository(database_path)

    assert reopened_repository.list_upcoming(from_time=now, limit=10) == [
        created
    ]


def test_list_upcoming_rejects_a_nonpositive_limit(tmp_path: Path) -> None:
    repository = SQLiteEventRepository(tmp_path / "events.sqlite3")

    with pytest.raises(ValueError, match="limit must be positive"):
        repository.list_upcoming(from_time=datetime.now(UTC), limit=0)


def test_list_upcoming_rejects_a_time_without_a_timezone(
    tmp_path: Path,
) -> None:
    repository = SQLiteEventRepository(tmp_path / "events.sqlite3")

    with pytest.raises(ValueError, match="from_time must include a timezone"):
        repository.list_upcoming(
            from_time=datetime(2026, 10, 23, 18, 0), limit=10
        )
