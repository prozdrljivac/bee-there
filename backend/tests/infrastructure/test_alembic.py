import sqlite3
from contextlib import closing
from pathlib import Path

from alembic import command
from alembic.config import Config

from infrastructure.migrations import upgrade_database


def test_upgrade_database_enables_write_ahead_logging(tmp_path: Path) -> None:
    database_path = tmp_path / "events.sqlite3"

    upgrade_database(database_path)

    with closing(sqlite3.connect(database_path)) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal_mode == "wal"


def test_migration_matches_sqlalchemy_metadata(tmp_path: Path) -> None:
    database_path = tmp_path / "events.sqlite3"
    config = Config("alembic.ini", toml_file="pyproject.toml")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "head")

    command.check(config)


def test_upgrade_head_creates_the_sources_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "database.sqlite3"
    config = Config("alembic.ini", toml_file="pyproject.toml")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")

    with closing(sqlite3.connect(database_path)) as connection:
        columns = connection.execute("PRAGMA table_info(sources)").fetchall()
        indexes = connection.execute("PRAGMA index_list(sources)").fetchall()

    assert [column[1] for column in columns] == [
        "id",
        "name",
        "base_url",
        "enabled",
    ]
    assert {index[1] for index in indexes} >= {"ix_sources_enabled"}


def test_events_reference_their_configured_source(tmp_path: Path) -> None:
    database_path = tmp_path / "database.sqlite3"
    config = Config("alembic.ini", toml_file="pyproject.toml")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")

    with closing(sqlite3.connect(database_path)) as connection:
        foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(events)"
        ).fetchall()

    assert [(key[2], key[3], key[4]) for key in foreign_keys] == [
        ("sources", "source_id", "id")
    ]


def test_upgrade_head_creates_the_events_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "events.sqlite3"
    config = Config("alembic.ini", toml_file="pyproject.toml")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")

    with closing(sqlite3.connect(database_path)) as connection:
        columns = connection.execute("PRAGMA table_info(events)").fetchall()
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]

    assert [column[1] for column in columns] == [
        "id",
        "title",
        "summary",
        "starts_at",
        "ends_at",
        "location_name",
        "source_id",
        "source_url",
        "external_id",
        "last_seen_at",
        "created_at",
        "updated_at",
    ]
    assert revision is not None
    assert journal_mode == "wal"
