"""Phase 1 global identity, tenant, and security-token ORM models.
Phase 2 salon operations core models (services, staff, customers).

This module intentionally defines persistence only. Authentication business flows,
JWTs, password hashing, and API endpoints belong to later Phase 1 tasks.
"""

import uuid
from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db import Base


class TimestampMixin:
    """Shared creation/update timestamps with database-side UTC-capable defaults."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class User(TimestampMixin, Base):
    """Global identity; it has no tenant foreign key or tenant role."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    is_super_admin: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    email_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    created_salons: Mapped[list["Salon"]] = relationship(
        back_populates="created_by", foreign_keys="Salon.created_by_user_id"
    )
    memberships: Mapped[list["SalonMembership"]] = relationship(back_populates="user")
    auth_sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user")
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(back_populates="user")

    @validates("email")
    def normalize_email(self, key: str, value: str) -> str:
        """Strip whitespace and convert to lowercase for case-insensitive uniqueness."""
        return value.strip().lower() if value else value


class Salon(TimestampMixin, Base):
    """Tenant root with minimal Phase 1 lifecycle state."""

    __tablename__ = "salons"
    __table_args__ = (
        CheckConstraint("status IN ('onboarding', 'active', 'suspended')", name="ck_salons_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="onboarding")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    created_by: Mapped["User"] = relationship(
        back_populates="created_salons", foreign_keys=[created_by_user_id]
    )
    memberships: Mapped[list["SalonMembership"]] = relationship(back_populates="salon")
    invitations: Mapped[list["SalonInvitation"]] = relationship(back_populates="salon")
    services: Mapped[list["SalonService"]] = relationship(back_populates="salon")
    customers: Mapped[list["SalonCustomer"]] = relationship(back_populates="salon")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="salon")
    branches: Mapped[list["Branch"]] = relationship(back_populates="salon")


class SalonMembership(TimestampMixin, Base):
    """Tenant-scoped role assignment; the only holder of tenant roles."""

    __tablename__ = "salon_memberships"
    __table_args__ = (
        UniqueConstraint("salon_id", "user_id", name="uq_salon_memberships_salon_user"),
        CheckConstraint("role IN ('owner', 'manager', 'staff')", name="ck_salon_memberships_role"),
        CheckConstraint("status IN ('active', 'suspended')", name="ck_salon_memberships_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    salon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salons.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    salon: Mapped["Salon"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="memberships")
    staff_profile: Mapped["StaffProfile"] = relationship(back_populates="membership", uselist=False)


class AuthSession(Base):
    """Rotating opaque refresh session metadata; token_hash never stores raw tokens."""

    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_family_id", "family_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_sessions.id", ondelete="RESTRICT"), nullable=True
    )
    user_agent: Mapped[str] = mapped_column(String(512), nullable=True)

    user: Mapped["User"] = relationship(back_populates="auth_sessions")


class SalonInvitation(Base):
    """Hashed, expiring invitation for manager/staff membership only."""

    __tablename__ = "salon_invitations"
    __table_args__ = (
        CheckConstraint("role IN ('manager', 'staff')", name="ck_salon_invitations_role"),
        Index("ix_salon_invitations_email", "email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    salon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salons.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    salon: Mapped["Salon"] = relationship(back_populates="invitations")


class PasswordResetToken(Base):
    """One-time reset token metadata; token_hash never stores raw tokens."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="password_reset_tokens")


# ============================================================================
# Phase 2: Salon Operations Core Models
# ============================================================================


class SalonService(TimestampMixin, Base):
    """Tenant-scoped service offering (haircut, facial, etc)."""

    __tablename__ = "salon_services"
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="ck_salon_services_duration_positive"),
        CheckConstraint("price_amount >= 0", name="ck_salon_services_price_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    salon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salons.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="IDR")
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")

    salon: Mapped["Salon"] = relationship(back_populates="services")
    staff_assignments: Mapped[list["StaffServiceAssignment"]] = relationship(
        back_populates="service"
    )
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="service")


class StaffProfile(TimestampMixin, Base):
    """Extended staff profile (one-to-one with SalonMembership).

    SalonMembership is the authoritative source for user_id and salon_id.
    This profile extends membership with operational booking metadata.
    """

    __tablename__ = "staff_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("salon_memberships.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    bio: Mapped[str] = mapped_column(String(1000), nullable=True)
    photo_url: Mapped[str] = mapped_column(String(512), nullable=True)
    is_bookable: Mapped[bool] = mapped_column(nullable=False, server_default="true")

    membership: Mapped["SalonMembership"] = relationship(back_populates="staff_profile")
    service_assignments: Mapped[list["StaffServiceAssignment"]] = relationship(
        back_populates="staff_profile"
    )
    weekly_availability: Mapped[list["StaffWeeklyAvailability"]] = relationship(
        back_populates="staff_profile"
    )
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="staff_profile")


class StaffServiceAssignment(TimestampMixin, Base):
    """Many-to-many: staff can perform specific services."""

    __tablename__ = "staff_service_assignments"
    __table_args__ = (
        UniqueConstraint(
            "staff_profile_id",
            "salon_service_id",
            name="uq_staff_service_assignments_staff_service",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    salon_service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("salon_services.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    staff_profile: Mapped["StaffProfile"] = relationship(back_populates="service_assignments")
    service: Mapped["SalonService"] = relationship(back_populates="staff_assignments")


class StaffWeeklyAvailability(TimestampMixin, Base):
    """Weekly recurring availability schedule for staff.

    Note: UNIQUE(staff_profile_id, day_of_week, start_time) prevents exact duplicates only.
    It does NOT prevent overlapping time slots. Overlap validation is an application-layer
    concern to be implemented in P2-D service logic with concurrency-safe tests.
    """

    __tablename__ = "staff_weekly_availability"
    __table_args__ = (
        CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name="ck_staff_weekly_availability_day_of_week",
        ),
        CheckConstraint("start_time < end_time", name="ck_staff_weekly_availability_time_order"),
        UniqueConstraint(
            "staff_profile_id",
            "day_of_week",
            "start_time",
            name="uq_staff_weekly_availability_staff_day_start",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_available: Mapped[bool] = mapped_column(nullable=False, server_default="true")

    staff_profile: Mapped["StaffProfile"] = relationship(back_populates="weekly_availability")


class SalonCustomer(TimestampMixin, Base):
    """Tenant-scoped customer record.

    Customers are scoped per salon. Email and phone are optional - a customer
    can be registered with just a name (walk-in scenario). Email/phone normalization
    and duplicate detection are service-layer concerns.
    """

    __tablename__ = "salon_customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    salon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salons.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    notes: Mapped[str] = mapped_column(String(1000), nullable=True)

    salon: Mapped["Salon"] = relationship(back_populates="customers")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="customer")


# ============================================================================
# Phase 3: Booking & Appointment Engine
# ============================================================================


class Appointment(TimestampMixin, Base):
    """Tenant-scoped appointment linking customer, service, and staff.

    Snapshots service metadata at booking time. Lifecycle: scheduled, confirmed,
    completed, cancelled, no_show. Terminal states cannot be reopened in Phase 3.
    Stores UTC instants with IANA timezone for local interpretation.
    """

    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show')",
            name="ck_appointments_status",
        ),
        CheckConstraint("ends_at > starts_at", name="ck_appointments_time_order"),
        CheckConstraint(
            "duration_minutes_snapshot > 0",
            name="ck_appointments_duration_snapshot_positive",
        ),
        CheckConstraint(
            "price_amount_snapshot >= 0",
            name="ck_appointments_price_snapshot_non_negative",
        ),
        Index("ix_appointments_starts_at", "starts_at"),
        Index("ix_appointments_salon_staff_starts_at", "salon_id", "staff_profile_id", "starts_at"),
        Index("ix_appointments_salon_status_starts_at", "salon_id", "status", "starts_at"),
        Index("ix_appointments_salon_customer_starts_at", "salon_id", "customer_id", "starts_at"),
        Index("ix_appointments_salon_service_starts_at", "salon_id", "service_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    salon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salons.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("salon_customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("salon_services.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    staff_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Time instants stored in UTC
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # IANA timezone for local interpretation (e.g., "Asia/Jakarta")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)

    # Service metadata snapshots
    service_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    duration_minutes_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    price_amount_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency_snapshot: Mapped[str] = mapped_column(String(3), nullable=False)

    # Lifecycle state
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="scheduled")

    # Optional booking notes
    notes: Mapped[str] = mapped_column(String(1000), nullable=True)

    # Relationships
    salon: Mapped["Salon"] = relationship(back_populates="appointments")
    customer: Mapped["SalonCustomer"] = relationship(back_populates="appointments")
    service: Mapped["SalonService"] = relationship(back_populates="appointments")
    staff_profile: Mapped["StaffProfile"] = relationship(back_populates="appointments")


# ============================================================================
# Phase 4: Multi-Location / Branch Operations
# ============================================================================


class Branch(TimestampMixin, Base):
    """Operational location inside a salon.

    Branch is tenant-scoped (salon_id). Each salon has one or more branches.
    Branch code is unique within salon and used for URL routing/identification.
    Timezone determines local scheduling interpretation for branch operations.
    """

    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("salon_id", "code", name="uq_branches_salon_code"),
        Index("ix_branches_salon_is_active", "salon_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    salon_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salons.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")

    salon: Mapped["Salon"] = relationship(back_populates="branches")
