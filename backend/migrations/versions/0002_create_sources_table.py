"""Create the sources table.

Revision ID: 0002_sources
Revises: 0001_events

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_sources"
down_revision: str | Sequence[str] | None = "0001_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the Sources schema."""
    op.create_table(
        "sources",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sources"),
        sa.UniqueConstraint("base_url", name="uq_sources_base_url"),
        sa.UniqueConstraint("name", name="uq_sources_name"),
    )
    op.create_index(
        "ix_sources_enabled",
        "sources",
        ["enabled"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the Sources schema."""
    op.drop_index("ix_sources_enabled", table_name="sources")
    op.drop_table("sources")
