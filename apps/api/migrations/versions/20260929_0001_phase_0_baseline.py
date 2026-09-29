"""Phase 0 migration foundation baseline.

Revision ID: 20260929_0001
Revises:
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create only the non-business migration validation table."""
    op.create_table(
        "platform_metadata",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_platform_metadata")),
    )


def downgrade() -> None:
    """Remove the Phase 0 migration validation table."""
    op.drop_table("platform_metadata")
