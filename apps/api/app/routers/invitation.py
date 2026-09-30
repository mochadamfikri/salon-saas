"""Invitation endpoints: create, list, revoke, accept."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.config import get_settings
from app.core.dependencies import get_db
from app.core.rate_limit import rate_limit
from app.core.rbac import Permission
from app.core.tenant import TenantContext, get_tenant_context
from app.models import User
from app.schemas.invitation import (
    InvitationAcceptRequest,
    InvitationAcceptResponse,
    InvitationCreateRequest,
    InvitationResponse,
)
from app.schemas.tenant import MembershipResponse, SalonResponse
from app.services.invitation import (
    DuplicateMembershipError,
    InvitationAlreadyAcceptedError,
    InvitationEmailMismatchError,
    InvitationExpiredError,
    InvitationNotFoundError,
    InvitationRevokedError,
    accept_invitation,
    create_invitation,
    list_salon_invitations,
    revoke_invitation,
)

router = APIRouter(tags=["invitations"])

_accept_rate_limit = rate_limit(
    get_settings().rate_limit_invitation_accept, prefix="invitation-accept"
)


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


@router.post(
    "/invitations/accept",
    response_model=InvitationAcceptResponse,
    dependencies=[Depends(_accept_rate_limit)],
)
def accept_invitation_endpoint(
    payload: InvitationAcceptRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InvitationAcceptResponse:
    """Accept an invitation and create an active membership.

    Canonical Phase 1 contract:
    - 200: {"membership": <MembershipResponse>, "salon": <SalonResponse>}
    - 401: unauthenticated (via the auth dependency)
    - 404: invalid/unknown token
    - 409: already accepted, or duplicate/existing membership
    - 410: expired or revoked invitation
    - 422: authenticated user email does not match the invitation email

    Invitation lifecycle failures are NOT collapsed into a generic 404.
    """
    try:
        membership, salon = accept_invitation(db, payload.token, current_user)
        db.commit()
        return InvitationAcceptResponse(
            membership=MembershipResponse.model_validate(membership),
            salon=SalonResponse.model_validate(salon),
        )
    except InvitationNotFoundError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None
    except InvitationAlreadyAcceptedError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from None
    except DuplicateMembershipError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from None
    except InvitationExpiredError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=str(e),
        ) from None
    except InvitationRevokedError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=str(e),
        ) from None
    except InvitationEmailMismatchError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from None
