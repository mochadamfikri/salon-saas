"""Pydantic schemas for staff profile and staff-service assignment endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StaffProfileCreateRequest(BaseModel):
    """Request payload for creating a staff profile."""

    membership_id: UUID


class StaffProfileUpdateRequest(BaseModel):
    """Request payload for updating a staff profile.

    Personal fields (display_name, phone, bio, photo_url) can be updated by:
    - Owner/Manager: any profile in the salon
    - Staff: their own profile only

    is_bookable can only be updated by Owner/Manager.
    Immutable fields are rejected rather than silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    bio: str | None = Field(default=None, max_length=1000)
    photo_url: str | None = Field(default=None, max_length=512)


class StaffProfileResponse(BaseModel):
    """Response representation of a staff profile."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    membership_id: UUID
    display_name: str | None
    phone: str | None
    bio: str | None
    photo_url: str | None
    is_bookable: bool
    created_at: datetime
    updated_at: datetime


class StaffProfileToggleBookableRequest(BaseModel):
    """Request payload for toggling is_bookable (Owner/Manager only)."""

    is_bookable: bool


class StaffServiceAssignmentResponse(BaseModel):
    """Response representation of a staff-service assignment."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    staff_profile_id: UUID
    salon_service_id: UUID
    created_at: datetime
    updated_at: datetime
