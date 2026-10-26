"""SQLite persistence for the Events module."""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from uuid import UUID, uuid7

from modules.events.contracts import EventDraft
from modules.events.domain import Event

Clock = Callable[[], datetime]
IdFactory = Callable[[], UUID]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_database_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _event_from_row(row: sqlite3.Row) -> Event:
    return Event(
        id=UUID(row["id"]),
        title=row["title"],
        summary=row["summary"],
        starts_at=datetime.fromisoformat(row["starts_at"]),
        ends_at=datetime.fromisoformat(row["ends_at"])
        if row["ends_at"]
        else None,
        location_name=row["location_name"],
        source_id=UUID(row["source_id"]),
        source_url=row["source_url"],
        external_id=row["external_id"],
        last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class SQLiteEventRepository:
    """Store canonical events in a SQLite database."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        clock: Clock = _utc_now,
        id_factory: IdFactory = uuid7,
    ) -> None:
        self._database_path = str(database_path)
        self._clock = clock
        self._id_factory = id_factory
        self._migrate()

    def upsert(self, draft: EventDraft) -> Event:
        """Insert an event or update the matching source listing."""
        now = self._clock().astimezone(UTC)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = self._find_existing(connection, draft)
            if existing is None:
                event = Event(
                    id=self._id_factory(),
                    title=draft.title,
                    summary=draft.summary,
                    starts_at=draft.starts_at,
                    ends_at=draft.ends_at,
                    location_name=draft.location_name,
                    source_id=draft.source_id,
                    source_url=draft.source_url,
                    external_id=draft.external_id,
                    last_seen_at=now,
                    created_at=now,
                    updated_at=now,
                )
                self._insert(connection, event)
                return event

            event = Event(
                id=existing.id,
                title=draft.title,
                summary=draft.summary,
                starts_at=draft.starts_at,
                ends_at=draft.ends_at,
                location_name=draft.location_name,
                source_id=draft.source_id,
                source_url=draft.source_url,
                external_id=draft.external_id,
                last_seen_at=now,
                created_at=existing.created_at,
                updated_at=now,
            )
            self._update(connection, event)
            return event

    def list_upcoming(self, *, from_time: datetime, limit: int) -> list[Event]:
        """Return events starting on or after a time, in chronological order."""
        if limit <= 0:
            raise ValueError("limit must be positive")
        if from_time.tzinfo is None or from_time.utcoffset() is None:
            raise ValueError("from_time must include a timezone")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM events
                WHERE starts_at >= ?
                ORDER BY starts_at, id
                LIMIT ?
                """,
                (_as_database_text(from_time), limit),
            ).fetchall()
        return [_event_from_row(row) for row in rows]

    def _find_existing(
        self, connection: sqlite3.Connection, draft: EventDraft
    ) -> Event | None:
        if draft.external_id is not None:
            row = connection.execute(
                "SELECT * FROM events WHERE source_id = ? AND external_id = ?",
                (str(draft.source_id), draft.external_id),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT * FROM events WHERE source_id = ? AND source_url = ? AND external_id IS NULL",
                (str(draft.source_id), draft.source_url),
            ).fetchone()
        return _event_from_row(row) if row is not None else None

    def _insert(self, connection: sqlite3.Connection, event: Event) -> None:
        connection.execute(
            """
            INSERT INTO events (
                id, title, summary, starts_at, ends_at, location_name,
                source_id, source_url, external_id, last_seen_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._event_values(event),
        )

    def _update(self, connection: sqlite3.Connection, event: Event) -> None:
        connection.execute(
            """
            UPDATE events SET
                title = ?, summary = ?, starts_at = ?, ends_at = ?, location_name = ?,
                source_url = ?, external_id = ?, last_seen_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                event.title,
                event.summary,
                _as_database_text(event.starts_at),
                _as_database_text(event.ends_at) if event.ends_at else None,
                event.location_name,
                event.source_url,
                event.external_id,
                _as_database_text(event.last_seen_at),
                _as_database_text(event.updated_at),
                str(event.id),
            ),
        )

    @staticmethod
    def _event_values(event: Event) -> tuple[str | None, ...]:
        return (
            str(event.id),
            event.title,
            event.summary,
            _as_database_text(event.starts_at),
            _as_database_text(event.ends_at) if event.ends_at else None,
            event.location_name,
            str(event.source_id),
            event.source_url,
            event.external_id,
            _as_database_text(event.last_seen_at),
            _as_database_text(event.created_at),
            _as_database_text(event.updated_at),
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _migrate(self) -> None:
        migration = files("modules.events.migrations").joinpath(
            "001_initial.sql"
        )
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                connection.executescript(migration.read_text(encoding="utf-8"))
            elif version != 1:
                raise RuntimeError(
                    f"unsupported Events database schema version: {version}"
                )
