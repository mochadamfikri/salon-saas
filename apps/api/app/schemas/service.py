"""Pydantic schemas for service catalog endpoints."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SalonServiceCreateRequest(BaseModel):
    """Request payload for creating a salon service."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=100)
    duration_minutes: int = Field(gt=0)
    price_amount: Decimal = Field(ge=0, decimal_places=2, max_digits=12)
    currency: str = Field(default="IDR", min_length=3, max_length=3)


class SalonServiceUpdateRequest(BaseModel):
    """Request payload for updating a salon service."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=100)
    duration_minutes: int | None = Field(default=None, gt=0)
    price_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2, max_digits=12)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class SalonServiceResponse(BaseModel):
    """Response representation of a salon service."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    salon_id: UUID
    name: str
    description: str | None
    category: str | None
    duration_minutes: int
    price_amount: Decimal
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
