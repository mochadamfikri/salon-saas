"""Pydantic schemas for tenant and membership endpoints."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

RESERVED_SALON_SLUGS = frozenset({"admin", "api", "auth", "docs", "health", "me", "salons"})


class SalonCreateRequest(BaseModel):
    """Payload for creating a salon; slug is optional."""

    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(
        default=None, min_length=3, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_and_validate_explicit_slug(cls, value: object) -> str | None:
        """Normalize explicit slugs and reject protected routes."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Slug must be a string")
        normalized = value.strip().lower()
        if normalized in RESERVED_SALON_SLUGS:
            raise ValueError("Slug is reserved")
        return normalized


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


class MemberStatusUpdateRequest(BaseModel):
    """Membership status update payload."""

    status: str = Field(pattern=r"^(active|suspended)$")
