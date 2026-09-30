"""Pydantic request and response models for authentication endpoints."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Registration payload."""

    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    """Credential login payload."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """Opaque refresh-token payload.

    The endpoint accepts any non-empty candidate then returns a generic 401 for
    invalid values, avoiding a format oracle for refresh credentials.
    """

    refresh_token: str = Field(min_length=1, max_length=512)


class TokenResponse(BaseModel):
    """New access and refresh tokens returned after authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Safe global user profile."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    is_active: bool
    is_super_admin: bool
