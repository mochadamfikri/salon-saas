"""Pydantic schemas for password reset endpoints."""

from pydantic import BaseModel, EmailStr, Field


class PasswordResetRequestPayload(BaseModel):
    """Payload for requesting password reset."""

    email: EmailStr


class PasswordResetConfirmPayload(BaseModel):
    """Payload for confirming password reset with token."""

    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=12, max_length=128)
