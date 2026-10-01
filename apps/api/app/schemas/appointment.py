"""Pydantic schemas for appointment endpoints."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppointmentCreateRequest(BaseModel):
    """Request payload for creating an appointment."""

    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    service_id: UUID
    staff_profile_id: UUID
    starts_at: datetime
    timezone: str = Field(..., max_length=64)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("starts_at")
    @classmethod
    def validate_starts_at_aware(cls, v: datetime) -> datetime:
        """Require timezone-aware datetime."""
        if v.tzinfo is None:
            raise ValueError("starts_at must be timezone-aware")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Trim timezone name."""
        if v is None:
            raise ValueError("timezone cannot be null")
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("timezone cannot be blank")
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


class AppointmentUpdateRequest(BaseModel):
    """Request payload for updating or rescheduling an appointment."""

    model_config = ConfigDict(extra="forbid")

    starts_at: datetime | None = None
    timezone: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("starts_at")
    @classmethod
    def validate_starts_at_aware(cls, v: datetime | None) -> datetime | None:
        """Require timezone-aware datetime if provided."""
        if v is not None and v.tzinfo is None:
            raise ValueError("starts_at must be timezone-aware")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        """Trim timezone name if provided."""
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("timezone cannot be blank")
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


AppointmentRescheduleRequest = AppointmentUpdateRequest


class AppointmentResponse(BaseModel):
    """Response representation of an appointment."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    salon_id: UUID
    customer_id: UUID
    service_id: UUID
    staff_profile_id: UUID
    starts_at: datetime
    ends_at: datetime
    timezone: str
    service_name_snapshot: str
    duration_minutes_snapshot: int
    price_amount_snapshot: Decimal
    currency_snapshot: str
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
