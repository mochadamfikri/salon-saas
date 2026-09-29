"""Phase 1 global identity, tenant, and security-token ORM models.

This module intentionally defines persistence only. Authentication business flows,
JWTs, password hashing, and API endpoints belong to later Phase 1 tasks.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
