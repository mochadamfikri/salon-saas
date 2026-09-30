"""Comprehensive password reset lifecycle and security tests."""

import uuid
from datetime import UTC, datetime, timedelta

from app.core.security import hash_password, verify_password
from app.main import app
from app.models import AuthSession, PasswordResetToken, User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

client = TestClient(app)


def test_password_reset_request_existing_user(db_session: Session):
    """Test password reset request for existing user returns generic success."""
    user = User(email="reset@example.com", password_hash=hash_password("OldPass123"), is_active=True)
    db_session.add(user)
    db_session.commit()

    response = client.post("/auth/password-reset/request", json={"email": "reset@example.com"})

    assert response.status_code == 200
    assert "email exists" in response.json()["message"].lower()

    # Verify token created in database
    token = db_session.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).first()
    assert token is not None
    assert token.used_at is None


def test_password_reset_request_nonexistent_user(db_session: Session):
    """Test password reset request for nonexistent user returns same generic response."""
    response = client.post("/auth/password-reset/request", json={"email": "nonexistent@example.com"})

    assert response.status_code == 200
    assert "email exists" in response.json()["message"].lower()

    # Verify no token created
    tokens = db_session.query(PasswordResetToken).all()
    assert len(tokens) == 0


def test_password_reset_request_inactive_user(db_session: Session):
    """Test password reset request for inactive user returns generic response (no token)."""
    user = User(
        email="inactive-reset@example.com",
        password_hash=hash_password("Pass123"),
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post("/auth/password-reset/request", json={"email": "inactive-reset@example.com"})

    assert response.status_code == 200

    # Verify no token created for inactive user
    token = db_session.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).first()
    assert token is None


def test_password_reset_confirm_success(db_session: Session):
    """Test successful password reset with valid token."""
    user = User(email="confirm@example.com", password_hash=hash_password("OldPass123"), is_active=True)
    db_session.add(user)
    db_session.commit()

    # Request reset
    request_response = client.post("/auth/password-reset/request", json={"email": "confirm@example.com"})
    assert request_response.status_code == 200

    # Get raw token from database (in production this would be emailed)
    from app.core.tokens import hash_token

    db_session.expire_all()
    reset_token = (
        db_session.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).first()
    )
    assert reset_token is not None

    # Generate a raw token for testing (in production client receives this via email)
    raw_token = "test_reset_token_" + str(reset_token.id)
    reset_token.token_hash = hash_token(raw_token)
    db_session.commit()

    # Confirm reset
    confirm_response = client.post(
        "/auth/password-reset/confirm",
        json={"token": raw_token, "new_password": "NewSecurePass123"},
    )

    assert confirm_response.status_code == 200
    assert "reset successfully" in confirm_response.json()["message"].lower()

    # Verify password changed
    db_session.expire(user)
    db_session.refresh(user)
    assert verify_password("NewSecurePass123", user.password_hash)
    assert not verify_password("OldPass123", user.password_hash)

    # Verify token marked as used
    db_session.refresh(reset_token)
    assert reset_token.used_at is not None


def test_password_reset_confirm_invalid_token(db_session: Session):
    """Test password reset with invalid token fails."""
    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": "invalid_token_12345", "new_password": "NewSecurePass123"},
    )

    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


def test_password_reset_confirm_expired_token(db_session: Session):
    """Test password reset with expired token fails."""
    user = User(email="expired@example.com", password_hash=hash_password("OldPass123"), is_active=True)
    db_session.add(user)
    db_session.commit()

    from app.core.tokens import generate_opaque_token, hash_token

    raw_token = generate_opaque_token()
    expired_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(expired_token)
    db_session.commit()

    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": raw_token, "new_password": "NewSecurePass123"},
    )

    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()


def test_password_reset_confirm_already_used_token(db_session: Session):
    """Test password reset with already-used token fails."""
    user = User(email="used@example.com", password_hash=hash_password("OldPass123"), is_active=True)
    db_session.add(user)
    db_session.commit()

    from app.core.config import get_settings
    from app.core.tokens import generate_opaque_token, hash_token

    settings = get_settings()
    raw_token = generate_opaque_token()
    used_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.password_reset_minutes),
        used_at=datetime.now(UTC),
    )
    db_session.add(used_token)
    db_session.commit()

    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": raw_token, "new_password": "NewSecurePass123"},
    )

    assert response.status_code == 400


def test_password_reset_revokes_existing_sessions(db_session: Session):
    """Test successful password reset revokes all existing sessions."""
    user = User(email="revoke-sessions@example.com", password_hash=hash_password("OldPass123"), is_active=True)
    db_session.add(user)
    db_session.commit()

    # Create active sessions
    from app.core.config import get_settings
    from app.core.tokens import generate_opaque_token, hash_token

    settings = get_settings()
    session1 = AuthSession(
        user_id=user.id,
        token_hash=hash_token(generate_opaque_token()),
        family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
    )
    session2 = AuthSession(
        user_id=user.id,
        token_hash=hash_token(generate_opaque_token()),
        family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
    )
    db_session.add_all([session1, session2])
    db_session.commit()

    # Create reset token
    raw_reset_token = generate_opaque_token()
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_reset_token),
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.password_reset_minutes),
    )
    db_session.add(reset_token)
    db_session.commit()

    # Confirm reset
    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": raw_reset_token, "new_password": "NewSecurePass123"},
    )

    assert response.status_code == 200

    # Verify all sessions revoked
    db_session.expire_all()
    active_sessions = (
        db_session.query(AuthSession)
        .filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .all()
    )
    assert len(active_sessions) == 0


def test_password_reset_weak_password_rejected(db_session: Session):
    """Test password reset with weak password fails validation."""
    user = User(email="weak-pass@example.com", password_hash=hash_password("OldPass123"), is_active=True)
    db_session.add(user)
    db_session.commit()

    from app.core.tokens import generate_opaque_token, hash_token

    raw_token = generate_opaque_token()
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(reset_token)
    db_session.commit()

    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": raw_token, "new_password": "short"},
    )

    assert response.status_code == 422  # Pydantic validation
