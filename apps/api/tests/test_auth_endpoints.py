"""Test authentication endpoints: register, login, refresh, logout, /auth/me."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from app.core.config import get_settings
from app.core.security import hash_password
from app.core.tokens import hash_token
from app.main import app
from app.models import AuthSession, User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

client = TestClient(app)


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        password_hash=hash_password("ValidPassword123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session: Session) -> User:
    """Create an inactive test user."""
    user = User(
        email="inactive@example.com",
        password_hash=hash_password("ValidPassword123"),
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_session(db_session: Session, test_user: User) -> tuple[AuthSession, str]:
    """Create a test session with raw token."""
    settings = get_settings()
    raw_token = "test_refresh_token_123456789012345678901234567890"  # 50 chars, meets >=32
    session = AuthSession(
        user_id=test_user.id,
        token_hash=hash_token(raw_token),
        family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session, raw_token


def test_register_success(db_session: Session):
    """Test successful user registration."""
    response = client.post(
        "/auth/register",
        json={"email": "newuser@example.com", "password": "SecurePass123"},
    )

    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Verify user created in database
    user = db_session.query(User).filter(User.email == "newuser@example.com").first()
    assert user is not None
    assert user.is_active is True


def test_register_duplicate_email(db_session: Session, test_user: User):
    """Test registration with existing email fails."""
    response = client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "AnotherPass123"},
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_register_weak_password():
    """Test registration with weak password fails."""
    response = client.post(
        "/auth/register",
        json={"email": "weak@example.com", "password": "short"},
    )

    assert response.status_code == 422  # Pydantic validation


def test_login_success(db_session: Session, test_user: User):
    """Test successful login with valid credentials."""
    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "ValidPassword123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Verify session created
    sessions = db_session.query(AuthSession).filter(AuthSession.user_id == test_user.id).all()
    assert len(sessions) == 1


def test_login_invalid_credentials(db_session: Session, test_user: User):
    """Test login with wrong password returns generic error."""
    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "WrongPassword"},
    )

    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


def test_login_nonexistent_email():
    """Test login with non-existent email returns generic error."""
    response = client.post(
        "/auth/login",
        json={"email": "nonexistent@example.com", "password": "SomePassword123"},
    )

    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


def test_login_inactive_user(db_session: Session, inactive_user: User):
    """Test login with inactive account fails."""
    response = client.post(
        "/auth/login",
        json={"email": "inactive@example.com", "password": "ValidPassword123"},
    )

    assert response.status_code == 403
    assert "not active" in response.json()["detail"].lower()


def test_refresh_token_success(
    db_session: Session, test_user: User, test_session: tuple[AuthSession, str]
):
    """Test refresh token rotation returns new tokens."""
    session, raw_token = test_session

    response = client.post("/auth/refresh", json={"refresh_token": raw_token})

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] != raw_token  # Rotated

    # Verify old session revoked
    db_session.refresh(session)
    assert session.revoked_at is not None

    # Verify new session created in same family
    new_sessions = (
        db_session.query(AuthSession)
        .filter(AuthSession.user_id == test_user.id, AuthSession.revoked_at.is_(None))
        .all()
    )
    assert len(new_sessions) == 1
    assert new_sessions[0].family_id == session.family_id


def test_refresh_token_invalid():
    """Test refresh with invalid token fails."""
    response = client.post("/auth/refresh", json={"refresh_token": "invalid_token"})

    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


def test_refresh_token_revoked(db_session: Session, test_session: tuple[AuthSession, str]):
    """Test refresh with revoked token fails."""
    session, raw_token = test_session
    session.revoked_at = datetime.now(UTC)
    db_session.commit()

    response = client.post("/auth/refresh", json={"refresh_token": raw_token})

    assert response.status_code == 401
    assert "revoked" in response.json()["detail"].lower()


def test_auth_me_success(db_session: Session, test_user: User):
    """Test /auth/me returns current user profile."""
    # Login to get access token
    login_response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "ValidPassword123"},
    )
    access_token = login_response.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["is_active"] is True
    assert "id" in data


def test_auth_me_no_token():
    """Test /auth/me without token returns 401."""
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_auth_me_invalid_token():
    """Test /auth/me with invalid token returns 401."""
    response = client.get("/auth/me", headers={"Authorization": "Bearer invalid"})

    assert response.status_code == 401


def test_auth_me_expired_token(db_session: Session, test_user: User):
    """Test /auth/me with expired token returns 401."""
    settings = get_settings()
    session = AuthSession(
        user_id=test_user.id,
        token_hash=hash_token("dummy"),
        family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.add(session)
    db_session.commit()

    # Create expired JWT
    expired_payload = {
        "sub": str(test_user.id),
        "sid": str(session.id),
        "typ": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int((datetime.now(UTC) - timedelta(hours=2)).timestamp()),
        "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    expired_token = jwt.encode(
        expired_payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})

    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_logout_success(db_session: Session, test_user: User):
    """Test logout revokes current session."""
    # Login
    login_response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "ValidPassword123"},
    )
    access_token = login_response.json()["access_token"]

    # Logout
    response = client.post("/auth/logout", headers={"Authorization": f"Bearer {access_token}"})

    assert response.status_code == 200
    assert "logged out" in response.json()["message"].lower()

    # Verify session revoked
    sessions = (
        db_session.query(AuthSession)
        .filter(AuthSession.user_id == test_user.id, AuthSession.revoked_at.is_(None))
        .all()
    )
    assert len(sessions) == 0


def test_logout_all_success(db_session: Session, test_user: User):
    """Test logout-all revokes all user sessions."""
    # Create two sessions
    login_response1 = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "ValidPassword123"},
    )
    access_token1 = login_response1.json()["access_token"]

    client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "ValidPassword123"},
    )

    # Logout all using first token
    response = client.post("/auth/logout-all", headers={"Authorization": f"Bearer {access_token1}"})

    assert response.status_code == 200
    data = response.json()
    assert data["revoked_count"] == 2

    # Verify all sessions revoked
    active_sessions = (
        db_session.query(AuthSession)
        .filter(AuthSession.user_id == test_user.id, AuthSession.revoked_at.is_(None))
        .all()
    )
    assert len(active_sessions) == 0
