"""Create the events table.

Revision ID: 0001_events
Revises:

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_events"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial Events schema."""
    op.create_table(
        "events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("starts_at", sa.String(), nullable=False),
        sa.Column("ends_at", sa.String(), nullable=True),
        sa.Column("location_name", sa.String(), nullable=True),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("last_seen_at", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at",
            name="ck_events_ends_after_start",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_events"),
    )
    op.create_index(
        "events_source_external_id_uq",
        "events",
        ["source_id", "external_id"],
        unique=True,
        sqlite_where=sa.text("external_id IS NOT NULL"),
    )
    op.create_index(
        "events_source_url_without_external_id_uq",
        "events",
        ["source_id", "source_url"],
        unique=True,
        sqlite_where=sa.text("external_id IS NULL"),
    )
    op.create_index(
        "events_starts_at_idx",
        "events",
        ["starts_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the Events schema."""
    op.drop_index("events_starts_at_idx", table_name="events")
    op.drop_index(
        "events_source_url_without_external_id_uq", table_name="events"
    )
    op.drop_index("events_source_external_id_uq", table_name="events")
    op.drop_table("events")
