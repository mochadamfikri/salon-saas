"""Pydantic request and response models for authentication endpoints."""

import re
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, EmailStr, Field, TypeAdapter, field_validator

from app.core.config import get_settings


def normalize_auth_email(value: str, app_env: str | None = None) -> str:
    environment = app_env or get_settings().app_env
    address = value.strip()
    try:
        return str(TypeAdapter(EmailStr).validate_python(address))
    except ValueError:
        if environment != "development":
            raise

    local_part, separator, domain = address.rpartition("@")
    if not separator or not domain.lower().endswith(".local"):
        raise ValueError("Enter a valid email address.")

    local_domain = domain[: -len(".local")]
    labels = local_domain.split(".")
    if not labels or any(
        len(label) > 63 or re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?", label) is None
        for label in labels
    ):
        raise ValueError("Enter a valid email address.")

    try:
        normalized_local = validate_email(
            f"{local_part}@preview.example.com", check_deliverability=False
        ).local_part
    except EmailNotValidError as error:
        raise ValueError("Enter a valid email address.") from error

    return f"{normalized_local}@{domain.lower()}"


class RegisterRequest(BaseModel):
    """Registration payload."""

    email: str
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_auth_email(value)


class LoginRequest(BaseModel):
    """Credential login payload."""

    email: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_auth_email(value)


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
