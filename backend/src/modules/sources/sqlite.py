"""SQLAlchemy persistence for the Sources module."""

from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid7

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from infrastructure.database import create_sqlite_engine
from infrastructure.persistence import (
    PersistenceConflictError,
    PersistenceError,
)
from modules.sources.contracts import SourceDraft, SourceUpdate
from modules.sources.domain import Source
from modules.sources.model import SourceRow

IdFactory = Callable[[], UUID]


def _source_from_row(row: SourceRow) -> Source:
    return Source(
        id=UUID(row.id),
        name=row.name,
        base_url=row.base_url,
        enabled=row.enabled,
    )


class SQLiteSourceRepository:
    """Store event sources in SQLite through SQLAlchemy."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        id_factory: IdFactory = uuid7,
    ) -> None:
        self._id_factory = id_factory
        self._sessions = sessionmaker(
            create_sqlite_engine(database_path),
            expire_on_commit=False,
        )

    def create(self, draft: SourceDraft) -> Source:
        """Create an event source."""
        row = SourceRow(
            id=str(self._id_factory()),
            name=draft.name,
            base_url=draft.base_url,
            enabled=draft.enabled,
        )
        try:
            with self._sessions.begin() as session:
                session.add(row)
                session.flush()
        except IntegrityError as error:
            raise PersistenceConflictError(
                "source conflicts with existing data"
            ) from error
        except SQLAlchemyError as error:
            raise PersistenceError("source persistence failed") from error
        return _source_from_row(row)

    def update(self, source_id: UUID, changes: SourceUpdate) -> Source | None:
        """Update one source if it exists."""
        try:
            with self._sessions.begin() as session:
                row = session.get(SourceRow, str(source_id))
                if row is None:
                    return None
                if "name" in changes.model_fields_set:
                    assert changes.name is not None
                    row.name = changes.name
                if "base_url" in changes.model_fields_set:
                    assert changes.base_url is not None
                    row.base_url = changes.base_url
                if "enabled" in changes.model_fields_set:
                    assert changes.enabled is not None
                    row.enabled = changes.enabled
                session.flush()
                return _source_from_row(row)
        except IntegrityError as error:
            raise PersistenceConflictError(
                "source conflicts with existing data"
            ) from error
        except SQLAlchemyError as error:
            raise PersistenceError("source persistence failed") from error

    def list_enabled(self) -> list[Source]:
        """Return enabled sources ordered by name."""
        statement = (
            select(SourceRow)
            .where(SourceRow.enabled.is_(True))
            .order_by(SourceRow.name, SourceRow.id)
        )
        try:
            with self._sessions() as session:
                rows = session.scalars(statement).all()
        except SQLAlchemyError as error:
            raise PersistenceError("source persistence failed") from error
        return [_source_from_row(row) for row in rows]

    def get(self, source_id: UUID) -> Source | None:
        """Return one source by ID."""
        try:
            with self._sessions() as session:
                row = session.get(SourceRow, str(source_id))
        except SQLAlchemyError as error:
            raise PersistenceError("source persistence failed") from error
        return _source_from_row(row) if row is not None else None

    def get_by_base_url(self, base_url: str) -> Source | None:
        """Return one source by its base URL."""
        statement = select(SourceRow).where(SourceRow.base_url == base_url)
        try:
            with self._sessions() as session:
                row = session.scalar(statement)
        except SQLAlchemyError as error:
            raise PersistenceError("source persistence failed") from error
        return _source_from_row(row) if row is not None else None
