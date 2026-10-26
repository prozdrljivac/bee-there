"""Add the primary event category.

Revision ID: 0004_event_category
Revises: 0003_event_source_fk

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_event_category"
down_revision: str | Sequence[str] | None = "0003_event_source_fk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Require a primary category for every event."""
    op.add_column(
        "events",
        sa.Column(
            "category",
            sa.String(),
            nullable=False,
            server_default="other",
        ),
    )


def downgrade() -> None:
    """Remove the primary event category."""
    op.drop_column("events", "category")
