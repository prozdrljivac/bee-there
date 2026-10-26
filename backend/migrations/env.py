"""Alembic migration environment."""

import sqlite3
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool

from modules.events.model import EventRow
from modules.sources.model import SourceRow

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_MAPPED_ROWS = (EventRow, SourceRow)
target_metadata = _MAPPED_ROWS[0].metadata


def configure_sqlite(
    connection: sqlite3.Connection, _connection_record: object
) -> None:
    """Configure a SQLite connection before Alembic starts a transaction."""
    previous_autocommit = connection.autocommit
    connection.autocommit = True
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode = WAL")
        journal_mode = cursor.fetchone()[0]
        cursor.execute("PRAGMA foreign_keys = ON")
    finally:
        cursor.close()
        connection.autocommit = previous_autocommit
    if journal_mode != "wal":
        raise RuntimeError("could not enable SQLite WAL mode")


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a database connection."""
    engine = create_engine(
        config.get_main_option("sqlalchemy.url"),
        connect_args={"autocommit": False},
        poolclass=NullPool,
    )
    event.listen(engine, "connect", configure_sqlite)

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
