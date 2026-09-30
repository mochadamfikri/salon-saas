"""Authentication and authorization dependencies."""

import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.tokens import decode_access_token
from app.models import AuthSession, User

security = HTTPBearer()


def get_current_user_and_session(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
) -> tuple[User, AuthSession]:
    """Validate JWT access token and load active user and session.

    Validates:
    - Token format and signature
    - Required claims: sub, sid, typ, iss, aud, exp, etc.
    - Session exists and is not revoked
    - User exists and is active

    Returns:
        Tuple of (User, AuthSession).

    Raises:
        HTTPException 401: Invalid token, revoked session, or inactive user.
    """
    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    # Validate claim types
    if payload.get("typ") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    session_id_str = payload.get("sid")

    if not user_id_str or not session_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(user_id_str)
        session_id = uuid.UUID(session_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    # Verify session is still active
    session = db.get(AuthSession, session_id)
    if not session or session.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify user is active
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user, session


def get_current_user(
    user_and_session: Annotated[tuple[User, AuthSession], Depends(get_current_user_and_session)],
) -> User:
    """Dependency that provides the authenticated active User."""
    return user_and_session[0]


def get_current_session(
    user_and_session: Annotated[tuple[User, AuthSession], Depends(get_current_user_and_session)],
) -> AuthSession:
    """Dependency that provides the current active AuthSession."""
    return user_and_session[1]
