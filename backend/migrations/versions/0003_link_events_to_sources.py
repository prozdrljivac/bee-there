"""Link events to configured sources.

Revision ID: 0003_event_source_fk
Revises: 0002_sources

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_event_source_fk"
down_revision: str | Sequence[str] | None = "0002_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Require every event to reference a configured source."""
    with op.batch_alter_table("events") as batch_op:
        batch_op.create_foreign_key(
            "fk_events_source_id_sources",
            "sources",
            ["source_id"],
            ["id"],
        )


def downgrade() -> None:
    """Remove the event source foreign key."""
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_constraint(
            "fk_events_source_id_sources",
            type_="foreignkey",
        )
