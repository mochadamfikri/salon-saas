"""Tenant endpoints: salon creation, membership listing, member management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.dependencies import get_db
from app.core.tenant import TenantContext, get_tenant_context
from app.models import SalonMembership, User
from app.schemas.tenant import (
    MemberRoleUpdateRequest,
    MembershipResponse,
    MySalonResponse,
    SalonCreateRequest,
    SalonResponse,
)
from app.services.tenant import (
    create_salon_with_owner,
    get_salon_members,
    get_user_salons,
    remove_member,
    update_member_role,
)

router = APIRouter(tags=["tenant"])


@router.post("/salons", response_model=SalonResponse, status_code=status.HTTP_201_CREATED)
def create_salon(
    payload: SalonCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SalonResponse:
    """Create a new salon and assign creator as OWNER."""
    try:
        salon, _ = create_salon_with_owner(db, payload.name, payload.slug, current_user)
        db.commit()
        return SalonResponse.model_validate(salon)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Salon slug already exists",
        ) from None


@router.get("/me/salons", response_model=list[MySalonResponse])
def get_my_salons(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[MySalonResponse]:
    """List current user's salon memberships."""
    memberships = get_user_salons(db, current_user.id)
    return [MySalonResponse.model_validate(m) for m in memberships]


@router.get("/salons/{salon_id}/members", response_model=list[MembershipResponse])
def list_salon_members(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> list[MembershipResponse]:
    """List all members of a salon (requires active membership)."""
    members = get_salon_members(tenant.db, tenant.salon.id)
    return [MembershipResponse.model_validate(m) for m in members]


@router.patch("/salons/{salon_id}/members/{membership_id}", response_model=MembershipResponse)
def update_member_role_endpoint(
    salon_id: UUID,
    membership_id: UUID,
    payload: MemberRoleUpdateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> MembershipResponse:
    """Update a member's role (owner only)."""
    tenant.require_owner()

    # Verify membership belongs to this salon
    membership = tenant.db.get(SalonMembership, membership_id)
    if not membership or membership.salon_id != salon_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this salon",
        )

    try:
        updated = update_member_role(tenant.db, membership_id, payload.role)
        tenant.db.commit()
        return MembershipResponse.model_validate(updated)
    except ValueError as e:
        tenant.db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from None


@router.delete("/salons/{salon_id}/members/{membership_id}", status_code=status.HTTP_200_OK)
def remove_member_endpoint(
    salon_id: UUID,
    membership_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> dict[str, str]:
    """Remove a member from salon (owner only)."""
    tenant.require_owner()

    # Verify membership belongs to this salon
    membership = tenant.db.get(SalonMembership, membership_id)
    if not membership or membership.salon_id != salon_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this salon",
        )

    try:
        remove_member(tenant.db, membership_id)
        tenant.db.commit()
        return {"message": "Member removed successfully"}
    except ValueError as e:
        tenant.db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from None
