"""Shared SQLAlchemy database configuration."""

import sqlite3
from pathlib import Path

from sqlalchemy import URL, Engine, MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _enable_sqlite_foreign_keys(
    connection: sqlite3.Connection, _connection_record: object
) -> None:
    previous_autocommit = connection.autocommit
    connection.autocommit = True
    try:
        connection.execute("PRAGMA foreign_keys = ON")
    finally:
        connection.autocommit = previous_autocommit


def create_sqlite_engine(database_path: str | Path) -> Engine:
    """Create a configured SQLAlchemy engine for one SQLite database."""
    database_url = URL.create(
        "sqlite", database=str(Path(database_path).resolve())
    )
    engine = create_engine(
        database_url,
        connect_args={"autocommit": False, "timeout": 5.0},
        poolclass=NullPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine
