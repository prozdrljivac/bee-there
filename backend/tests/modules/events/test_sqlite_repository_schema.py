import sqlite3
from contextlib import closing
from pathlib import Path

from modules.events.sqlite import SQLiteEventRepository


def test_repository_does_not_manage_the_database_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "events.sqlite3"

    SQLiteEventRepository(database_path)

    with closing(sqlite3.connect(database_path)) as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE name = 'events'"
        ).fetchone()
    assert table is None
