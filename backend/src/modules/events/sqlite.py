"""SQLAlchemy persistence for the Events module."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid7

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from infrastructure.database import create_sqlite_engine
from infrastructure.persistence import (
    PersistenceConflictError,
    PersistenceError,
)
from modules.events.contracts import EventDraft
from modules.events.domain import Event
from modules.events.model import EventRow

Clock = Callable[[], datetime]
IdFactory = Callable[[], UUID]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_database_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _event_from_row(row: EventRow) -> Event:
    return Event(
        id=UUID(row.id),
        title=row.title,
        summary=row.summary,
        starts_at=datetime.fromisoformat(row.starts_at),
        ends_at=datetime.fromisoformat(row.ends_at) if row.ends_at else None,
        location_name=row.location_name,
        source_id=UUID(row.source_id),
        source_url=row.source_url,
        external_id=row.external_id,
        last_seen_at=datetime.fromisoformat(row.last_seen_at),
        created_at=datetime.fromisoformat(row.created_at),
        updated_at=datetime.fromisoformat(row.updated_at),
    )


class SQLiteEventRepository:
    """Store canonical events in SQLite through SQLAlchemy."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        clock: Clock = _utc_now,
        id_factory: IdFactory = uuid7,
    ) -> None:
        self._clock = clock
        self._id_factory = id_factory
        self._sessions = sessionmaker(
            create_sqlite_engine(database_path),
            expire_on_commit=False,
        )

    def upsert(self, draft: EventDraft) -> Event:
        """Insert an event or update the matching source listing."""
        try:
            return self._upsert(draft)
        except IntegrityError as error:
            raise PersistenceConflictError(
                "event conflicts with existing data"
            ) from error
        except SQLAlchemyError as error:
            raise PersistenceError("event persistence failed") from error

    def _upsert(self, draft: EventDraft) -> Event:
        now = self._clock().astimezone(UTC)
        with self._sessions.begin() as session:
            row = self._find_existing(session, draft)
            if row is None:
                row = EventRow(
                    id=str(self._id_factory()),
                    title=draft.title,
                    summary=draft.summary,
                    starts_at=_as_database_text(draft.starts_at),
                    ends_at=(
                        _as_database_text(draft.ends_at)
                        if draft.ends_at
                        else None
                    ),
                    location_name=draft.location_name,
                    source_id=str(draft.source_id),
                    source_url=draft.source_url,
                    external_id=draft.external_id,
                    last_seen_at=_as_database_text(now),
                    created_at=_as_database_text(now),
                    updated_at=_as_database_text(now),
                )
                session.add(row)
            else:
                row.title = draft.title
                row.summary = draft.summary
                row.starts_at = _as_database_text(draft.starts_at)
                row.ends_at = (
                    _as_database_text(draft.ends_at) if draft.ends_at else None
                )
                row.location_name = draft.location_name
                row.source_url = draft.source_url
                if draft.external_id is not None:
                    row.external_id = draft.external_id
                row.last_seen_at = _as_database_text(now)
                row.updated_at = _as_database_text(now)
            session.flush()
            return _event_from_row(row)

    def list_upcoming(self, *, from_time: datetime, limit: int) -> list[Event]:
        """Return events starting on or after a time, in chronological order."""
        if limit <= 0:
            raise ValueError("limit must be positive")
        if from_time.tzinfo is None or from_time.utcoffset() is None:
            raise ValueError("from_time must include a timezone")

        statement = (
            select(EventRow)
            .where(EventRow.starts_at >= _as_database_text(from_time))
            .order_by(EventRow.starts_at, EventRow.id)
            .limit(limit)
        )
        try:
            with self._sessions() as session:
                rows = session.scalars(statement).all()
        except SQLAlchemyError as error:
            raise PersistenceError("event persistence failed") from error
        return [_event_from_row(row) for row in rows]

    @staticmethod
    def _find_existing(session: Session, draft: EventDraft) -> EventRow | None:
        if draft.external_id is not None:
            statement = select(EventRow).where(
                EventRow.source_id == str(draft.source_id),
                EventRow.external_id == draft.external_id,
            )
            row = session.scalar(statement)
            if row is not None:
                return row

        statement = select(EventRow).where(
            EventRow.source_id == str(draft.source_id),
            EventRow.source_url == draft.source_url,
        )
        if draft.external_id is not None:
            statement = statement.where(EventRow.external_id.is_(None))
        return session.scalar(statement)
