"""Add database-enforced case-insensitive user email uniqueness.

Revision ID: 2317437c36e3
Revises: 20260929_0002
Create Date: 2026-09-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "2317437c36e3"
down_revision: str | Sequence[str] | None = "20260929_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Reject case-variant emails, including writes outside SQLAlchemy ORM."""
    op.execute("CREATE UNIQUE INDEX uq_users_lower_email ON users (LOWER(email))")


def downgrade() -> None:
    """Remove the database-level normalized-email invariant."""
    op.execute("DROP INDEX IF EXISTS uq_users_lower_email")
