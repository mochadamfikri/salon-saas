"""Phase 3 Booking & Appointment Engine core.

Revision ID: 9ecad5e4f77e
Revises: 547d2dd43298
Create Date: 2026-10-01 19:19:19.787496
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9ecad5e4f77e"
down_revision: str | Sequence[str] | None = "547d2dd43298"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create the tenant-scoped appointment domain table and lookup indexes."""
    op.create_table(
        "appointments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("salon_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID(), nullable=False),
        sa.Column("staff_profile_id", sa.UUID(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("service_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("duration_minutes_snapshot", sa.Integer(), nullable=False),
        sa.Column("price_amount_snapshot", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency_snapshot", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="scheduled", nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show')",
            name="ck_appointments_status",
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_appointments_time_order"),
        sa.CheckConstraint(
            "duration_minutes_snapshot > 0",
            name="ck_appointments_duration_snapshot_positive",
        ),
        sa.CheckConstraint(
            "price_amount_snapshot >= 0",
            name="ck_appointments_price_snapshot_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["salon_id"],
            ["salons.id"],
            name=op.f("fk_appointments_salon_id_salons"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["salon_customers.id"],
            name=op.f("fk_appointments_customer_id_salon_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["salon_services.id"],
            name=op.f("fk_appointments_service_id_salon_services"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["staff_profile_id"],
            ["staff_profiles.id"],
            name=op.f("fk_appointments_staff_profile_id_staff_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointments")),
    )
    op.create_index(op.f("ix_appointments_salon_id"), "appointments", ["salon_id"], unique=False)
    op.create_index(
        op.f("ix_appointments_customer_id"), "appointments", ["customer_id"], unique=False
    )
    op.create_index(
        op.f("ix_appointments_service_id"), "appointments", ["service_id"], unique=False
    )
    op.create_index(
        op.f("ix_appointments_staff_profile_id"),
        "appointments",
        ["staff_profile_id"],
        unique=False,
    )
    op.create_index(op.f("ix_appointments_starts_at"), "appointments", ["starts_at"], unique=False)
    op.create_index(
        "ix_appointments_salon_staff_starts_at",
        "appointments",
        ["salon_id", "staff_profile_id", "starts_at"],
        unique=False,
    )
    op.create_index(
        "ix_appointments_salon_status_starts_at",
        "appointments",
        ["salon_id", "status", "starts_at"],
        unique=False,
    )
    op.create_index(
        "ix_appointments_salon_customer_starts_at",
        "appointments",
        ["salon_id", "customer_id", "starts_at"],
        unique=False,
    )
    op.create_index(
        "ix_appointments_salon_service_starts_at",
        "appointments",
        ["salon_id", "service_id", "starts_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the Phase 3 appointment table and its indexes."""
    op.drop_index("ix_appointments_salon_service_starts_at", table_name="appointments")
    op.drop_index("ix_appointments_salon_customer_starts_at", table_name="appointments")
    op.drop_index("ix_appointments_salon_status_starts_at", table_name="appointments")
    op.drop_index("ix_appointments_salon_staff_starts_at", table_name="appointments")
    op.drop_index(op.f("ix_appointments_starts_at"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_staff_profile_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_service_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_customer_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_salon_id"), table_name="appointments")
    op.drop_table("appointments")
