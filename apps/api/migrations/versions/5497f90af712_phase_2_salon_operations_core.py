"""Phase 2 Salon Operations Core.

Revision ID: 5497f90af712
Revises: 2317437c36e3
Create Date: 2026-09-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5497f90af712"
down_revision: str | Sequence[str] | None = "2317437c36e3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create Phase 2 Salon Operations Core tables."""
    # salon_services
    op.create_table(
        "salon_services",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("salon_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("price_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
        sa.ForeignKeyConstraint(
            ["salon_id"],
            ["salons.id"],
            name=op.f("fk_salon_services_salon_id_salons"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_salon_services")),
        sa.UniqueConstraint("salon_id", "name", name="uq_salon_services_salon_name"),
    )
    op.create_index(
        op.f("ix_salon_services_salon_id"), "salon_services", ["salon_id"], unique=False
    )

    # staff_profiles
    op.create_table(
        "staff_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("membership_id", sa.UUID(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("bio", sa.String(length=1000), nullable=True),
        sa.Column("photo_url", sa.String(length=512), nullable=True),
        sa.Column("is_bookable", sa.Boolean(), server_default="true", nullable=False),
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
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["salon_memberships.id"],
            name=op.f("fk_staff_profiles_membership_id_salon_memberships"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_profiles")),
        sa.UniqueConstraint("membership_id", name=op.f("uq_staff_profiles_membership_id")),
    )
    op.create_index(
        op.f("ix_staff_profiles_membership_id"), "staff_profiles", ["membership_id"], unique=False
    )

    # staff_service_assignments
    op.create_table(
        "staff_service_assignments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("staff_profile_id", sa.UUID(), nullable=False),
        sa.Column("salon_service_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["salon_service_id"],
            ["salon_services.id"],
            name=op.f("fk_staff_service_assignments_salon_service_id_salon_services"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["staff_profile_id"],
            ["staff_profiles.id"],
            name=op.f("fk_staff_service_assignments_staff_profile_id_staff_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_service_assignments")),
        sa.UniqueConstraint(
            "staff_profile_id",
            "salon_service_id",
            name="uq_staff_service_assignments_staff_service",
        ),
    )
    op.create_index(
        op.f("ix_staff_service_assignments_salon_service_id"),
        "staff_service_assignments",
        ["salon_service_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staff_service_assignments_staff_profile_id"),
        "staff_service_assignments",
        ["staff_profile_id"],
        unique=False,
    )

    # staff_weekly_availability
    op.create_table(
        "staff_weekly_availability",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("staff_profile_id", sa.UUID(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
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
            "day_of_week >= 1 AND day_of_week <= 7",
            name="ck_staff_weekly_availability_day_of_week",
        ),
        sa.ForeignKeyConstraint(
            ["staff_profile_id"],
            ["staff_profiles.id"],
            name=op.f("fk_staff_weekly_availability_staff_profile_id_staff_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_weekly_availability")),
        sa.UniqueConstraint(
            "staff_profile_id",
            "day_of_week",
            "start_time",
            name="uq_staff_weekly_availability_staff_day_start",
        ),
    )
    op.create_index(
        op.f("ix_staff_weekly_availability_staff_profile_id"),
        "staff_weekly_availability",
        ["staff_profile_id"],
        unique=False,
    )

    # salon_customers
    op.create_table(
        "salon_customers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("salon_id", sa.UUID(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["salon_id"],
            ["salons.id"],
            name=op.f("fk_salon_customers_salon_id_salons"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_salon_customers")),
        sa.UniqueConstraint("salon_id", "email", name="uq_salon_customers_salon_email"),
    )
    op.create_index(
        op.f("ix_salon_customers_salon_id"), "salon_customers", ["salon_id"], unique=False
    )


def downgrade() -> None:
    """Drop Phase 2 Salon Operations Core tables."""
    op.drop_index(op.f("ix_salon_customers_salon_id"), table_name="salon_customers")
    op.drop_table("salon_customers")
    op.drop_index(
        op.f("ix_staff_weekly_availability_staff_profile_id"),
        table_name="staff_weekly_availability",
    )
    op.drop_table("staff_weekly_availability")
    op.drop_index(
        op.f("ix_staff_service_assignments_staff_profile_id"),
        table_name="staff_service_assignments",
    )
    op.drop_index(
        op.f("ix_staff_service_assignments_salon_service_id"),
        table_name="staff_service_assignments",
    )
    op.drop_table("staff_service_assignments")
    op.drop_index(op.f("ix_staff_profiles_membership_id"), table_name="staff_profiles")
    op.drop_table("staff_profiles")
    op.drop_index(op.f("ix_salon_services_salon_id"), table_name="salon_services")
    op.drop_table("salon_services")
