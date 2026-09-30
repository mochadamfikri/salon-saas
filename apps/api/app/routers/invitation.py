"""Invitation endpoints: create, list, revoke, accept."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.dependencies import get_db
from app.core.rbac import Permission
from app.core.tenant import TenantContext, get_tenant_context
from app.models import User
from app.schemas.invitation import (
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationResponse,
)
from app.schemas.tenant import MembershipResponse
from app.services.invitation import (
    DuplicateMembershipError,
    InvitationNotFoundError,
    accept_invitation,
    create_invitation,
    list_salon_invitations,
    revoke_invitation,
)

router = APIRouter(tags=["invitations"])


@router.post(
    "/salons/{salon_id}/invitations",
    response_model=dict[str, str],
    status_code=status.HTTP_201_CREATED,
)
def create_invitation_endpoint(
    salon_id: UUID,
    payload: InvitationCreateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> dict[str, str]:
    """Create a new salon invitation (owner invites manager/staff; manager invites staff only)."""
    # RBAC: OWNER can invite manager/staff, MANAGER can invite staff only
    if payload.role == "manager":
        tenant.require_permission(Permission.INVITE_MANAGER)
    else:
        tenant.require_permission(Permission.INVITE_STAFF)

    invitation, raw_token = create_invitation(
        tenant.db, tenant.salon, payload.email, payload.role, tenant.user.id
    )
    tenant.db.commit()

    return {
        "message": "Invitation created successfully",
        "invitation_id": str(invitation.id),
        "token": raw_token,
    }


@router.get("/salons/{salon_id}/invitations", response_model=list[InvitationResponse])
def list_invitations_endpoint(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> list[InvitationResponse]:
    """List all salon invitations (owner or manager only)."""
    tenant.require_permission(Permission.VIEW_MEMBERS)
    invitations = list_salon_invitations(tenant.db, tenant.salon.id)
    return [InvitationResponse.model_validate(inv) for inv in invitations]


@router.delete("/salons/{salon_id}/invitations/{invitation_id}", status_code=status.HTTP_200_OK)
def revoke_invitation_endpoint(
    salon_id: UUID,
    invitation_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> dict[str, str]:
    """Revoke a pending invitation (owner or manager)."""
    tenant.require_permission(Permission.VIEW_MEMBERS)

    try:
        revoke_invitation(tenant.db, invitation_id, salon_id)
        tenant.db.commit()
        return {"message": "Invitation revoked successfully"}
    except InvitationNotFoundError as e:
        tenant.db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None


@router.post("/invitations/accept", response_model=MembershipResponse)
def accept_invitation_endpoint(
    payload: InvitationAcceptRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MembershipResponse:
    """Accept an invitation and create active membership."""
    try:
        membership = accept_invitation(db, payload.token, current_user)
        db.commit()
        return MembershipResponse.model_validate(membership)
    except InvitationNotFoundError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None
    except DuplicateMembershipError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from None
