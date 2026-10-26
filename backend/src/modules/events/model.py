"""SQLAlchemy model owned by the Events module."""

from sqlalchemy import CheckConstraint, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base


class EventRow(Base):
    """Persisted representation of an event."""

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at",
            name="ends_after_start",
        ),
        Index(
            "events_source_external_id_uq",
            "source_id",
            "external_id",
            unique=True,
            sqlite_where=text("external_id IS NOT NULL"),
        ),
        Index(
            "events_source_url_without_external_id_uq",
            "source_id",
            "source_url",
            unique=True,
            sqlite_where=text("external_id IS NULL"),
        ),
        Index("events_starts_at_idx", "starts_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(String)
    starts_at: Mapped[str] = mapped_column(String)
    ends_at: Mapped[str | None] = mapped_column(String, nullable=True)
    location_name: Mapped[str | None] = mapped_column(String, nullable=True)
    source_id: Mapped[str] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(String)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    last_seen_at: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)
