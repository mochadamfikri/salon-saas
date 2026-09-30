"""Authentication service layer: registration, login, session management."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.core.tokens import create_access_token, generate_opaque_token, hash_token
from app.models import AuthSession, User


class AuthError(Exception):
    """Base authentication error."""


class InvalidCredentialsError(AuthError):
    """Generic credential failure (no email enumeration)."""


class InactiveUserError(AuthError):
    """User account is not active."""


class InvalidRefreshTokenError(AuthError):
    """Refresh token invalid, expired, revoked, or reused."""


def register_user(db: Session, email: str, password: str) -> User:
    """Register a new user with normalized email and hashed password.

    Args:
        db: Database session.
        email: User email (will be normalized).
        password: Plaintext password.

    Returns:
        Created User instance.

    Raises:
        ValueError: If email already exists (IntegrityError).
    """
    user = User(
        email=email,  # ORM @validates will normalize
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Authenticate user by email and password.

    Args:
        db: Database session.
        email: User email.
        password: Plaintext password.

    Returns:
        Authenticated User instance.

    Raises:
        InvalidCredentialsError: Generic error (no email enumeration).
        InactiveUserError: User exists but is not active.
    """
    normalized_email = email.strip().lower()
    stmt = select(User).where(User.email == normalized_email)
    user = db.execute(stmt).scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid email or password")

    if not user.is_active:
        raise InactiveUserError("Account is not active")

    # Update last login timestamp
    user.last_login_at = datetime.now(UTC)
    db.flush()

    return user


def create_session(db: Session, user: User) -> tuple[str, str, uuid.UUID]:
    """Create a new refresh session and tokens for the user.

    Args:
        db: Database session.
        user: Authenticated User.

    Returns:
        Tuple of (access_token, refresh_token, session_id).
    """
    settings = get_settings()

    # Generate new family and raw refresh token
    family_id = uuid.uuid4()
    raw_refresh = generate_opaque_token()

    # Create session with hashed token
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        family_id=family_id,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
    )
    db.add(session)
    db.flush()

    # Create JWT access token
    access_token = create_access_token(user.id, session.id)

    return access_token, raw_refresh, session.id


def refresh_session(db: Session, raw_refresh_token: str) -> tuple[str, str, User, uuid.UUID]:
    """Rotate refresh token and issue new access token.

    Implements family/reuse detection:
    - If token is valid and not expired: rotate and return new tokens.
    - If token is revoked or reused (family exists but token mismatches): revoke entire family.

    Args:
        db: Database session.
        raw_refresh_token: Raw opaque refresh token.

    Returns:
        Tuple of (new_access_token, new_refresh_token, user, new_session_id).

    Raises:
        InvalidRefreshTokenError: Token invalid, expired, revoked, or reused.
    """
    token_hash_value = hash_token(raw_refresh_token)
    now = datetime.now(UTC)

    # Find session by token hash
    stmt = select(AuthSession).where(AuthSession.token_hash == token_hash_value)
    session = db.execute(stmt).scalar_one_or_none()

    if not session:
        # Token not found — could be reuse attack
        # Attempt to find family and revoke if exists
        raise InvalidRefreshTokenError("Invalid refresh token")

    # Check if already revoked
    if session.revoked_at is not None:
        # Token was revoked — revoke entire family as reuse detection
        _revoke_family(db, session.family_id)
        raise InvalidRefreshTokenError("Refresh token has been revoked")

    # Check expiration
    if session.expires_at < now:
        raise InvalidRefreshTokenError("Refresh token expired")

    # Token is valid — revoke current session and create new one in same family
    session.revoked_at = now
    db.flush()

    # Load user
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise InactiveUserError("User account is not active")

    # Create new session with rotated token in same family
    settings = get_settings()
    new_raw_refresh = generate_opaque_token()
    new_session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(new_raw_refresh),
        family_id=session.family_id,  # Same family
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
    )
    db.add(new_session)
    db.flush()

    new_access_token = create_access_token(user.id, new_session.id)

    return new_access_token, new_raw_refresh, user, new_session.id


def revoke_session(db: Session, session_id: uuid.UUID) -> None:
    """Revoke a single session by ID (logout).

    Args:
        db: Database session.
        session_id: Session UUID to revoke.
    """
    session = db.get(AuthSession, session_id)
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        db.flush()


def revoke_all_user_sessions(db: Session, user_id: uuid.UUID) -> int:
    """Revoke all active sessions for a user (logout all).

    Args:
        db: Database session.
        user_id: User UUID.

    Returns:
        Number of sessions revoked.
    """
    now = datetime.now(UTC)
    stmt = select(AuthSession).where(
        and_(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    )
    sessions = db.execute(stmt).scalars().all()

    count = 0
    for session in sessions:
        session.revoked_at = now
        count += 1

    db.flush()
    return count


def _revoke_family(db: Session, family_id: uuid.UUID) -> None:
    """Revoke all sessions in a token family (reuse detection)."""
    now = datetime.now(UTC)
    stmt = select(AuthSession).where(
        and_(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
    )
    sessions = db.execute(stmt).scalars().all()

    for session in sessions:
        session.revoked_at = now

    db.flush()
