"""Password reset service layer: generic issuance and one-time redemption."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.core.tokens import generate_opaque_token, hash_token
from app.models import PasswordResetToken, User
from app.services.auth import revoke_all_user_sessions


class InvalidPasswordResetTokenError(Exception):
    """Reset token invalid, expired, or already used."""


def issue_password_reset_token(db: Session, email: str) -> str | None:
    """Issue a raw reset token for an existing active user, otherwise return None.

    The endpoint intentionally exposes the same generic response for either
    result; callers must not use this function as an enumeration oracle.
    """
    normalized_email = email.strip().lower()
    user = db.execute(select(User).where(User.email == normalized_email)).scalar_one_or_none()
    if not user or not user.is_active:
        return None

    settings = get_settings()
    raw_token = generate_opaque_token()
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.password_reset_minutes),
    )
    db.add(reset_token)
    db.flush()
    return raw_token


def reset_password(db: Session, raw_token: str, new_password: str) -> User:
    """Redeem an unexpired, unused reset token and revoke existing sessions.

    Concurrency-safe: the reset token row is locked (SELECT ... FOR UPDATE) so
    concurrent redemptions of the same token serialize — the loser observes
    ``used_at`` and is rejected, preserving one-time semantics.
    """
    now = datetime.now(UTC)
    token_hash_value = hash_token(raw_token)
    reset_token = db.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash_value)
        .with_for_update()
    ).scalar_one_or_none()

    if not reset_token or reset_token.used_at is not None or reset_token.expires_at < now:
        raise InvalidPasswordResetTokenError("Invalid or expired reset token")

    user = db.get(User, reset_token.user_id)
    if not user or not user.is_active:
        raise InvalidPasswordResetTokenError("Invalid or expired reset token")

    # Set used marker before updating credential so a successful transaction has one-time semantics.
    reset_token.used_at = now
    user.password_hash = hash_password(new_password)
    revoke_all_user_sessions(db, user.id)
    db.flush()
    return user
