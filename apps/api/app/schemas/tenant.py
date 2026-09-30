"""Pydantic schemas for tenant and membership endpoints."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SalonCreateRequest(BaseModel):
    """Payload for creating a salon."""

    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        """Normalize whitespace and require a lowercase URL-safe slug."""
        return value.strip().lower()


class SalonResponse(BaseModel):
    """Safe salon representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    status: str


class MemberUserResponse(BaseModel):
    """Safe nested user representation in a membership."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str


class MembershipResponse(BaseModel):
    """Safe tenant membership representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    status: str
    user: MemberUserResponse


class MySalonResponse(BaseModel):
    """Current user's membership plus salon representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    status: str
    salon: SalonResponse


class MemberRoleUpdateRequest(BaseModel):
    """Allowed non-owner role update payload."""

    role: str = Field(pattern=r"^(manager|staff)$")
