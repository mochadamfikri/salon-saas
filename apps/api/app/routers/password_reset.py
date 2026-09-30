"""Password reset endpoints: request, confirm."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_db
from app.core.rate_limit import rate_limit
from app.schemas.password_reset import PasswordResetConfirmPayload, PasswordResetRequestPayload
from app.services.password_reset import (
    InvalidPasswordResetTokenError,
    issue_password_reset_token,
    reset_password,
)

router = APIRouter(prefix="/auth/password-reset", tags=["password-reset"])

_password_reset_rate_limit = rate_limit(
    get_settings().rate_limit_password_reset, prefix="password-reset"
)


@router.post("/request", dependencies=[Depends(_password_reset_rate_limit)])
def request_password_reset(
    payload: PasswordResetRequestPayload,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Issue password reset token for an active user.

    Returns a generic success response regardless of whether the email exists
    to prevent email enumeration attacks.
    """
    # The raw token is intentionally NOT returned to the client and is never
    # logged: in production it must be delivered to the user via email inside
    # this request handler (TODO: wire the email provider). For Phase 1 the
    # token is only recoverable from the database (hash-only storage).
    issue_password_reset_token(db, payload.email)
    db.commit()

    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/confirm", dependencies=[Depends(_password_reset_rate_limit)])
def confirm_password_reset(
    payload: PasswordResetConfirmPayload,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Reset password using a valid one-time token."""
    try:
        reset_password(db, payload.token, payload.new_password)
        db.commit()
        return {"message": "Password reset successfully"}
    except InvalidPasswordResetTokenError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        ) from None
