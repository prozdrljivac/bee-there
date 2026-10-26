from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from infrastructure.migrations import upgrade_database
from modules.sources import SourceDraft, SourceUpdate
from modules.sources.sqlite import SQLiteSourceRepository


@pytest.fixture(autouse=True)
def migrate_database(tmp_path: Path) -> None:
    upgrade_database(tmp_path / "database.sqlite3")


def test_create_stores_a_source(tmp_path: Path) -> None:
    source_id = UUID("019a57c0-8800-7000-8000-000000000001")
    repository = SQLiteSourceRepository(
        tmp_path / "database.sqlite3",
        id_factory=lambda: source_id,
    )

    source = repository.create(
        SourceDraft(
            name="Cultural Station",
            base_url="https://example.com/events",
        )
    )

    assert source.id == source_id
    assert source.name == "Cultural Station"
    assert source.base_url == "https://example.com/events"
    assert source.enabled is True


@pytest.mark.parametrize("duplicate_field", ("name", "base_url"))
def test_create_rejects_duplicate_names_and_base_urls(
    tmp_path: Path,
    duplicate_field: str,
) -> None:
    repository = SQLiteSourceRepository(tmp_path / "database.sqlite3")
    original = SourceDraft(
        name="Cultural Station",
        base_url="https://example.com/events",
    )
    repository.create(original)
    duplicate_data = {
        "name": "Another Source",
        "base_url": "https://other.example.com/events",
        duplicate_field: getattr(original, duplicate_field),
    }

    with pytest.raises(IntegrityError):
        repository.create(SourceDraft.model_validate(duplicate_data))


def test_update_changes_a_stored_source(tmp_path: Path) -> None:
    repository = SQLiteSourceRepository(tmp_path / "database.sqlite3")
    created = repository.create(
        SourceDraft(
            name="Cultural Station",
            base_url="https://example.com/events",
        )
    )

    updated = repository.update(
        created.id,
        SourceUpdate(
            name="Updated Station",
            base_url="https://example.com/programme",
            enabled=False,
        ),
    )

    assert updated is not None
    assert updated.id == created.id
    assert updated.name == "Updated Station"
    assert updated.base_url == "https://example.com/programme"
    assert updated.enabled is False
    assert repository.get(created.id) == updated


def test_update_preserves_fields_that_are_not_supplied(tmp_path: Path) -> None:
    repository = SQLiteSourceRepository(tmp_path / "database.sqlite3")
    created = repository.create(
        SourceDraft(
            name="Cultural Station",
            base_url="https://example.com/events",
        )
    )

    updated = repository.update(
        created.id,
        SourceUpdate(base_url="https://example.com/programme"),
    )

    assert updated is not None
    assert updated.name == created.name
    assert updated.base_url == "https://example.com/programme"
    assert updated.enabled is True


def test_update_returns_none_for_an_unknown_source(tmp_path: Path) -> None:
    repository = SQLiteSourceRepository(tmp_path / "database.sqlite3")

    updated = repository.update(UUID(int=0), SourceUpdate(enabled=False))

    assert updated is None


def test_list_enabled_filters_and_orders_sources_by_name(
    tmp_path: Path,
) -> None:
    repository = SQLiteSourceRepository(tmp_path / "database.sqlite3")
    for name, enabled in (
        ("Zrenjanin Events", True),
        ("Disabled Source", False),
        ("Cultural Station", True),
    ):
        repository.create(
            SourceDraft(
                name=name,
                base_url=f"https://example.com/{name.lower().replace(' ', '-')}",
                enabled=enabled,
            )
        )

    sources = repository.list_enabled()

    assert [source.name for source in sources] == [
        "Cultural Station",
        "Zrenjanin Events",
    ]


def test_get_by_base_url_returns_a_stored_source(tmp_path: Path) -> None:
    repository = SQLiteSourceRepository(tmp_path / "database.sqlite3")
    created = repository.create(
        SourceDraft(
            name="Moj Novi Sad",
            base_url="https://www.mojnovisad.com/",
        )
    )

    assert repository.get_by_base_url("https://www.mojnovisad.com/") == created
    assert repository.get_by_base_url("https://unknown.example/") is None


def test_get_returns_none_for_an_unknown_source(tmp_path: Path) -> None:
    repository = SQLiteSourceRepository(tmp_path / "database.sqlite3")

    assert repository.get(UUID(int=0)) is None


def test_get_returns_a_stored_source(tmp_path: Path) -> None:
    source_id = UUID("019a57c0-8800-7000-8000-000000000001")
    repository = SQLiteSourceRepository(
        tmp_path / "database.sqlite3",
        id_factory=lambda: source_id,
    )
    created = repository.create(
        SourceDraft(
            name="Cultural Station",
            base_url="https://example.com/events",
        )
    )

    assert repository.get(source_id) == created
