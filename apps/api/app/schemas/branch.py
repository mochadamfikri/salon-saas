"""Pydantic schemas for branch endpoints."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

RESERVED_BRANCH_CODES = frozenset({"admin", "api", "default", "main"})


class BranchCreateRequest(BaseModel):
    """Request payload for creating a branch."""

    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    timezone: str = Field(min_length=1, max_length=64)
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_and_validate_code(cls, value: object) -> str:
        """Normalize code and reject reserved values."""
        if not isinstance(value, str):
            raise ValueError("Code must be a string")
        normalized = value.strip().lower()
        if normalized in RESERVED_BRANCH_CODES:
            raise ValueError("Code is reserved")
        return normalized


class BranchUpdateRequest(BaseModel):
    """Request payload for updating a branch."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=20)


class BranchActivateRequest(BaseModel):
    """Request payload for activating/deactivating a branch."""

    is_active: bool


class BranchResponse(BaseModel):
    """Response representation of a branch."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    salon_id: UUID
    name: str
    code: str
    timezone: str
    address: str | None
    phone: str | None
    is_active: bool
