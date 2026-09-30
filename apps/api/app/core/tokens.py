"""JWT and opaque refresh token services."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import get_settings


def create_access_token(user_id: uuid.UUID, session_id: uuid.UUID) -> str:
    """Create a short-lived JWT access token with required claims.

    Args:
        user_id: Global user UUID.
        session_id: Active auth_session UUID.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_minutes)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "sid": str(session_id),
        "typ": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded payload dict.

    Raises:
        jwt.PyJWTError: If token is invalid, expired, or claims don't match.
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["sub", "sid", "typ", "iss", "aud", "iat", "exp", "jti"]},
    )


def generate_opaque_token() -> str:
    """Generate a high-entropy cryptographically secure random token string."""
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    """Hash a raw token using SHA-256 for secure storage at rest."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
