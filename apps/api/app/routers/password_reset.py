"""Password reset endpoints: request, confirm."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.schemas.password_reset import PasswordResetConfirmPayload, PasswordResetRequestPayload
from app.services.password_reset import InvalidPasswordResetTokenError, issue_password_reset_token, reset_password

router = APIRouter(prefix="/auth/password-reset", tags=["password-reset"])


@router.post("/request")
def request_password_reset(
    payload: PasswordResetRequestPayload,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Issue password reset token for an active user.
    
    Returns a generic success response regardless of whether the email exists
    to prevent email enumeration attacks.
    """
    raw_token = issue_password_reset_token(db, payload.email)
    db.commit()
    
    # In production, send raw_token via email to payload.email if raw_token is not None.
    # For Phase 1 development, the token is logged but not returned to the client.
    
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/confirm")
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
