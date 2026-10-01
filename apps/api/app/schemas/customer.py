"""Pydantic schemas for customer endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CustomerCreateRequest(BaseModel):
    """Request payload for creating a salon customer."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(..., max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        """Validate full_name is non-empty after trimming."""
        if v is None:
            raise ValueError("full_name cannot be null")
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("full_name cannot be blank")
        return trimmed

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        """Trim, lowercase, and normalize empty string to None."""
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            return None
        return trimmed.lower()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """Trim and normalize empty string to None."""
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            return None
        return trimmed

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: str | None) -> str | None:
        """Trim and normalize empty string to None."""
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            return None
        return trimmed


class CustomerUpdateRequest(BaseModel):
    """Request payload for updating a salon customer."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str | None) -> str:
        """Explicit null or blank string for full_name is rejected."""
        if v is None:
            raise ValueError("full_name cannot be null")
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("full_name cannot be blank")
        return trimmed

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        """Trim, lowercase, and normalize empty string to None."""
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            return None
        return trimmed.lower()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """Trim and normalize empty string to None."""
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            return None
        return trimmed

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: str | None) -> str | None:
        """Trim and normalize empty string to None."""
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            return None
        return trimmed


class CustomerResponse(BaseModel):
    """Response representation of a salon customer."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    salon_id: UUID
    full_name: str
    email: str | None
    phone: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
