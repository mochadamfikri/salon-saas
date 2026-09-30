"""Pydantic schemas for invitation endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.tenant import MembershipResponse, SalonResponse


class InvitationCreateRequest(BaseModel):
    """Payload for creating a salon invitation."""

    email: EmailStr
    role: str = Field(pattern=r"^(manager|staff)$")


class InvitationResponse(BaseModel):
    """Safe invitation representation (token never included)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    salon_id: UUID
    email: str
    role: str
    invited_by_user_id: UUID
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


class InvitationAcceptRequest(BaseModel):
    """Payload for accepting an invitation."""

    token: str = Field(min_length=1, max_length=512)


class InvitationAcceptResponse(BaseModel):
    """Success payload: created membership plus the invitation's salon.

    The salon is the one belonging to the accepted invitation, loaded
    server-side. The client never supplies a salon_id to the accept endpoint.
    """

    membership: MembershipResponse
    salon: SalonResponse
