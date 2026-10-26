from pathlib import Path

from infrastructure.database import create_sqlite_engine


def test_sqlite_engine_enables_foreign_keys(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "database.sqlite3")
    try:
        with engine.connect() as connection:
            foreign_keys = connection.exec_driver_sql(
                "PRAGMA foreign_keys"
            ).scalar_one()
    finally:
        engine.dispose()

    assert foreign_keys == 1
