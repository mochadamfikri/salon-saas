"""Authentication endpoints: register, login, refresh, logout, /auth/me."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_session, get_current_user
from app.core.config import get_settings
from app.core.dependencies import get_db
from app.core.rate_limit import rate_limit
from app.models import AuthSession, User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    authenticate_user,
    create_session,
    refresh_session,
    register_user,
    revoke_all_user_sessions,
    revoke_session,
)

router = APIRouter(prefix="/auth", tags=["authentication"])

_settings = get_settings()
_register_rate_limit = rate_limit(_settings.rate_limit_register, prefix="auth-register")
_login_rate_limit = rate_limit(_settings.rate_limit_login, prefix="auth-login")
_refresh_rate_limit = rate_limit(_settings.rate_limit_refresh, prefix="auth-refresh")


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_register_rate_limit)],
)
def register(
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Register a new user and return access + refresh tokens."""
    try:
        user = register_user(db, payload.email, payload.password)
        access_token, refresh_token, _ = create_session(db, user)
        db.commit()
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        ) from None


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(_login_rate_limit)])
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Authenticate user and return access + refresh tokens."""
    try:
        user = authenticate_user(db, payload.email, payload.password)
        access_token, refresh_token, _ = create_session(db, user)
        db.commit()
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from None
    except InactiveUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active",
        ) from None


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(_refresh_rate_limit)])
def refresh(
    payload: RefreshRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Rotate refresh token and issue new access token."""
    try:
        access_token, refresh_token, _, _ = refresh_session(db, payload.refresh_token)
        db.commit()
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
    except (InvalidRefreshTokenError, InactiveUserError):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        ) from None


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return authenticated user profile."""
    return UserResponse.model_validate(current_user)


@router.post("/logout")
def logout(
    current_session: Annotated[AuthSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Revoke current session (logout)."""
    revoke_session(db, current_session.id)
    db.commit()
    return {"message": "Successfully logged out"}


@router.post("/logout-all")
def logout_all(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str | int]:
    """Revoke all user sessions (logout from all devices)."""
    count = revoke_all_user_sessions(db, current_user.id)
    db.commit()
    return {"message": "Logged out from all sessions", "revoked_count": count}
