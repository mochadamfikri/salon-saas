"""Pydantic schemas for staff weekly availability endpoints."""

from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AvailabilityCreateRequest(BaseModel):
    """Request payload for creating a weekly availability slot."""

    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    start_time: time
    end_time: time

    @field_validator("day_of_week")
    @classmethod
    def validate_day_of_week(cls, v: int) -> int:
        """Validate day_of_week is in valid range."""
        if not 0 <= v <= 6:
            raise ValueError("day_of_week must be between 0 and 6")
        return v

    @field_validator("end_time")
    @classmethod
    def validate_time_order(cls, v: time, info) -> time:
        """Validate start_time < end_time."""
        if "start_time" in info.data:
            start_time = info.data["start_time"]
            if start_time >= v:
                raise ValueError("start_time must be less than end_time")
        return v


class AvailabilityUpdateRequest(BaseModel):
    """Request payload for updating a weekly availability slot."""

    day_of_week: int | None = Field(
        None, ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)"
    )
    start_time: time | None = None
    end_time: time | None = None

    @field_validator("day_of_week")
    @classmethod
    def validate_day_of_week(cls, v: int | None) -> int | None:
        """Validate day_of_week is in valid range if provided."""
        if v is not None and not 0 <= v <= 6:
            raise ValueError("day_of_week must be between 0 and 6")
        return v


class AvailabilityResponse(BaseModel):
    """Response representation of a weekly availability slot."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    staff_profile_id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    is_available: bool
    created_at: datetime
    updated_at: datetime
