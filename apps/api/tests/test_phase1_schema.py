"""Tests for Phase 1 database schema foundation, constraints, and dependencies."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from app.core.dependencies import get_db
from app.db import engine
from app.models import (
    AuthSession,
    Salon,
    SalonMembership,
    User,
)
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError


def test_phase1_tables_exist() -> None:
    """Verify all 6 Phase 1 tables exist in the database."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "platform_metadata",
        "users",
        "salons",
        "salon_memberships",
        "auth_sessions",
        "salon_invitations",
        "password_reset_tokens",
    }
    assert expected_tables.issubset(table_names)


def test_get_db_session_dependency() -> None:
    """Verify get_db dependency yields an active SQLAlchemy Session and closes it."""
    generator = get_db()
    session = next(generator)
    real_close = session.close
    close_spy = MagicMock(side_effect=real_close)
    session.close = close_spy

    try:
        assert session.is_active
        # Execute a lightweight probe
        result = session.execute(select(1)).scalar()
        assert result == 1
    finally:
        with pytest.raises(StopIteration):
            next(generator)
    assert close_spy.call_count == 1


def test_user_email_is_normalized_and_unique_case_insensitively() -> None:
    """Verify normalized email is lower-cased and cannot be duplicated by case."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]
    normalized_email = f"user_{unique_suffix}@example.com"
    mixed_case_email = f"  User_{unique_suffix}@Example.COM  "

    try:
        user1 = User(
            id=uuid.uuid4(),
            email=mixed_case_email,
            password_hash="argon2id$placeholder$hash1",
        )
        session.add(user1)
        session.commit()
        assert user1.email == normalized_email

        user2 = User(
            id=uuid.uuid4(),
            email=normalized_email,
            password_hash="argon2id$placeholder$hash2",
        )
        session.add(user2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.query(User).filter(User.email == normalized_email).delete()
        session.commit()
        session.close()


def test_salon_slug_uniqueness() -> None:
    """Verify duplicate salon slug is rejected by unique constraint."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]
    slug = f"salon-{unique_suffix}"

    try:
        creator = User(
            id=uuid.uuid4(),
            email=f"creator_{unique_suffix}@example.com",
            password_hash="argon2id$placeholder$creator",
        )
        session.add(creator)
        session.commit()

        salon1 = Salon(
            id=uuid.uuid4(),
            name="Salon One",
            slug=slug,
            created_by_user_id=creator.id,
        )
        session.add(salon1)
        session.commit()

        # Attempt to insert identical slug
        salon2 = Salon(
            id=uuid.uuid4(),
            name="Salon Duplicate Slug",
            slug=slug,
            created_by_user_id=creator.id,
        )
        session.add(salon2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.query(Salon).filter(Salon.slug == slug).delete()
        session.query(User).filter(User.id == creator.id).delete()
        session.commit()
        session.close()


def test_salon_membership_unique_salon_user() -> None:
    """Verify UNIQUE(salon_id, user_id) constraint prevents duplicate membership."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]

    try:
        owner = User(
            id=uuid.uuid4(),
            email=f"owner_{unique_suffix}@example.com",
            password_hash="argon2id$placeholder$owner",
        )
        session.add(owner)
        session.commit()

        salon = Salon(
            id=uuid.uuid4(),
            name="Test Salon",
            slug=f"test-salon-{unique_suffix}",
            created_by_user_id=owner.id,
        )
        session.add(salon)
        session.commit()

        membership1 = SalonMembership(
            id=uuid.uuid4(),
            salon_id=salon.id,
            user_id=owner.id,
            role="owner",
            status="active",
        )
        session.add(membership1)
        session.commit()

        # Attempt duplicate membership for same (salon_id, user_id)
        membership2 = SalonMembership(
            id=uuid.uuid4(),
            salon_id=salon.id,
            user_id=owner.id,
            role="manager",
            status="active",
        )
        session.add(membership2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.query(SalonMembership).filter(SalonMembership.salon_id == salon.id).delete()
        session.query(Salon).filter(Salon.id == salon.id).delete()
        session.query(User).filter(User.id == owner.id).delete()
        session.commit()
        session.close()


def test_foreign_key_restricts_deletion() -> None:
    """Verify ondelete='RESTRICT' prevents deleting parent entity when children exist."""
    generator = get_db()
    session = next(generator)
    unique_suffix = uuid.uuid4().hex[:8]

    try:
        user = User(
            id=uuid.uuid4(),
            email=f"fk_test_{unique_suffix}@example.com",
            password_hash="argon2id$placeholder$fk",
        )
        session.add(user)
        session.commit()

        session_record = AuthSession(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=f"token_hash_{unique_suffix}",
            family_id=uuid.uuid4(),
            expires_at=datetime.now(UTC),
        )
        session.add(session_record)
        session.commit()

        # Attempting to delete user without removing auth_sessions must fail with IntegrityError
        session.delete(user)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.query(AuthSession).filter(AuthSession.user_id == user.id).delete()
        session.query(User).filter(User.id == user.id).delete()
        session.commit()
        session.close()
