"""SQLAlchemy persistence for the Events module."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path
from uuid import UUID, uuid7

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from infrastructure.database import create_sqlite_engine
from infrastructure.persistence import (
    PersistenceConflictError,
    PersistenceError,
)
from modules.events.contracts import EventDraft, TimeRange
from modules.events.domain import Event, EventCategory
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
        category=EventCategory(row.category),
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


def _validate_pagination(limit: int, offset: int) -> None:
    if limit <= 0:
        raise ValueError("limit must be positive")
    if offset < 0:
        raise ValueError("offset must be non-negative")


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
                    category=draft.category.value,
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
                row.category = draft.category.value
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

    def list_upcoming(
        self,
        *,
        time_range: TimeRange,
        limit: int = 20,
        q: str | None = None,
        categories: Sequence[EventCategory] = (),
        offset: int = 0,
    ) -> list[Event]:
        """Return events overlapping the interval, in stable chronological order."""
        _validate_pagination(limit, offset)

        statement = (
            select(EventRow)
            .where(
                or_(
                    EventRow.ends_at > _as_database_text(time_range.from_time),
                    and_(
                        EventRow.ends_at.is_(None),
                        EventRow.starts_at
                        >= _as_database_text(time_range.from_time),
                    ),
                )
            )
            .order_by(EventRow.starts_at, EventRow.id)
        )
        if time_range.to_time is not None:
            statement = statement.where(
                EventRow.starts_at < _as_database_text(time_range.to_time)
            )
        if categories:
            statement = statement.where(EventRow.category.in_(categories))
        if not q:
            statement = statement.limit(limit).offset(offset)
        try:
            with self._sessions() as session:
                rows = session.scalars(statement)
                if q:
                    query = q.casefold()
                    matches = (
                        row for row in rows if query in row.title.casefold()
                    )
                    return [
                        _event_from_row(row)
                        for row in islice(matches, offset, offset + limit)
                    ]
                return [_event_from_row(row) for row in rows]
        except SQLAlchemyError as error:
            raise PersistenceError("event persistence failed") from error

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
