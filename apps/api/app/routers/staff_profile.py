"""Tenant-scoped Staff Profile and Staff-Service Assignment API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.core.tenant import TenantContext, get_tenant_context
from app.models import StaffProfile, StaffServiceAssignment
from app.schemas.staff_profile import (
    StaffProfileCreateRequest,
    StaffProfileResponse,
    StaffProfileToggleBookableRequest,
    StaffProfileUpdateRequest,
    StaffServiceAssignmentResponse,
)
from app.services.staff_profile import (
    create_staff_profile,
    create_staff_service_assignment,
    delete_staff_service_assignment,
    get_staff_profile,
    get_staff_service_assignment,
    list_staff_profiles,
    list_staff_service_assignments,
    toggle_staff_bookable,
    update_staff_profile,
)

router = APIRouter(tags=["staff-profiles"])


def _is_expected_duplicate_error(error: IntegrityError, constraint_name: str) -> bool:
    """Return whether an IntegrityError is the expected named UNIQUE constraint."""
    diagnostics = getattr(getattr(error, "orig", None), "diag", None)
    return getattr(diagnostics, "constraint_name", None) == constraint_name


def _require_profile_creation_permission(tenant: TenantContext) -> None:
    """Require Owner or Manager role for creating staff profiles."""
    tenant.require_owner_or_manager()


def _require_profile_mutation_permission(
    tenant: TenantContext,
    profile: StaffProfile,
) -> None:
    """Require permission to mutate a staff profile.

    Owner/Manager: can update any profile in the salon.
    Staff: can only update their own profile.
    """
    # Owner/Manager can update any profile
    if tenant.role in ("owner", "manager"):
        return

    # Staff can only update their own profile
    if profile.membership.user_id == tenant.user.id:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You can only update your own profile",
    )


def _require_bookable_toggle_permission(tenant: TenantContext) -> None:
    """Require Owner or Manager role for toggling is_bookable."""
    tenant.require_owner_or_manager()


def _require_assignment_mutation_permission(tenant: TenantContext) -> None:
    """Require Owner or Manager role for staff-service assignment mutation."""
    tenant.require_owner_or_manager()


def _get_tenant_profile_or_404(
    tenant: TenantContext,
    staff_profile_id: UUID,
) -> StaffProfile:
    """Load one staff profile only when it belongs to the current tenant."""
    profile = get_staff_profile(tenant.db, staff_profile_id, tenant.salon.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff profile not found",
        )
    return profile


def _get_tenant_assignment_or_404(
    tenant: TenantContext,
    staff_profile_id: UUID,
    service_id: UUID,
) -> StaffServiceAssignment:
    """Load one assignment only when it belongs to the current tenant."""
    assignment = get_staff_service_assignment(
        tenant.db,
        staff_profile_id,
        service_id,
        tenant.salon.id,
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment not found",
        )
    return assignment


# ============================================================================
# Staff Profile Endpoints
# ============================================================================


@router.post(
    "/salons/{salon_id}/staff-profiles",
    response_model=StaffProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_staff_profile_endpoint(
    payload: StaffProfileCreateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> StaffProfileResponse:
    """Create a staff profile for a membership in the current salon.

    Only Owner/Manager can create profiles.
    Target membership must be active and from the same salon.
    One membership can only have one profile (409 on duplicate).
    """
    _require_profile_creation_permission(tenant)
    try:
        profile = create_staff_profile(
            tenant.db,
            membership_id=payload.membership_id,
            salon_id=tenant.salon.id,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower() or "does not belong" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            ) from None
        if "already has" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg,
            ) from None
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_msg,
        ) from None
    except IntegrityError as e:
        tenant.db.rollback()
        if _is_expected_duplicate_error(e, "staff_profiles_membership_id_key"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Membership already has a staff profile",
            ) from None
        raise

    try:
        tenant.db.commit()
    except IntegrityError as e:
        tenant.db.rollback()
        if _is_expected_duplicate_error(e, "staff_profiles_membership_id_key"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Membership already has a staff profile",
            ) from None
        raise

    return StaffProfileResponse.model_validate(profile)


@router.get(
    "/salons/{salon_id}/staff-profiles",
    response_model=list[StaffProfileResponse],
)
def list_staff_profiles_endpoint(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> list[StaffProfileResponse]:
    """List all staff profiles in the current salon.

    All roles can read profiles in their salon.
    """
    profiles = list_staff_profiles(tenant.db, tenant.salon.id)
    return [StaffProfileResponse.model_validate(p) for p in profiles]


@router.get(
    "/salons/{salon_id}/staff-profiles/{staff_profile_id}",
    response_model=StaffProfileResponse,
)
def get_staff_profile_endpoint(
    staff_profile_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> StaffProfileResponse:
    """Get a staff profile belonging to the current salon.

    All roles can read profiles in their salon.
    """
    profile = _get_tenant_profile_or_404(tenant, staff_profile_id)
    return StaffProfileResponse.model_validate(profile)


@router.patch(
    "/salons/{salon_id}/staff-profiles/{staff_profile_id}",
    response_model=StaffProfileResponse,
)
def update_staff_profile_endpoint(
    staff_profile_id: UUID,
    payload: StaffProfileUpdateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> StaffProfileResponse:
    """Update personal fields of a staff profile.

    Owner/Manager: can update any profile in the salon.
    Staff: can only update their own profile.

    Personal fields (display_name, phone, bio, photo_url) can be updated.
    Explicit null clears the field; omitted fields are unchanged.
    is_bookable cannot be changed via this endpoint (use toggle endpoint).
    """
    profile = _get_tenant_profile_or_404(tenant, staff_profile_id)
    _require_profile_mutation_permission(tenant, profile)

    updated = update_staff_profile(
        tenant.db,
        profile,
        **payload.model_dump(exclude_unset=True),
    )
    tenant.db.commit()
    return StaffProfileResponse.model_validate(updated)


@router.post(
    "/salons/{salon_id}/staff-profiles/{staff_profile_id}/toggle-bookable",
    response_model=StaffProfileResponse,
)
def toggle_staff_bookable_endpoint(
    staff_profile_id: UUID,
    payload: StaffProfileToggleBookableRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> StaffProfileResponse:
    """Toggle is_bookable flag for a staff profile.

    Only Owner/Manager can toggle this operational flag.
    """
    _require_bookable_toggle_permission(tenant)
    profile = _get_tenant_profile_or_404(tenant, staff_profile_id)

    updated = toggle_staff_bookable(tenant.db, profile, payload.is_bookable)
    tenant.db.commit()
    return StaffProfileResponse.model_validate(updated)


# ============================================================================
# Staff-Service Assignment Endpoints
# ============================================================================


@router.post(
    "/salons/{salon_id}/staff-profiles/{staff_profile_id}/services/{service_id}",
    response_model=StaffServiceAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment_endpoint(
    staff_profile_id: UUID,
    service_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> StaffServiceAssignmentResponse:
    """Assign a service to a staff profile.

    Only Owner/Manager can create assignments.
    Staff and service must belong to the same salon (cross-salon guard).
    Duplicate assignment returns 409.
    """
    _require_assignment_mutation_permission(tenant)
    try:
        assignment = create_staff_service_assignment(
            tenant.db,
            staff_profile_id=staff_profile_id,
            service_id=service_id,
            salon_id=tenant.salon.id,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower() or "does not belong" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            ) from None
        if "already exists" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg,
            ) from None
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_msg,
        ) from None
    except IntegrityError as e:
        tenant.db.rollback()
        if _is_expected_duplicate_error(e, "uq_staff_service_assignments_staff_service"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Assignment already exists",
            ) from None
        raise

    try:
        tenant.db.commit()
    except IntegrityError as e:
        tenant.db.rollback()
        if _is_expected_duplicate_error(e, "uq_staff_service_assignments_staff_service"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Assignment already exists",
            ) from None
        raise

    return StaffServiceAssignmentResponse.model_validate(assignment)


@router.get(
    "/salons/{salon_id}/staff-profiles/{staff_profile_id}/services",
    response_model=list[StaffServiceAssignmentResponse],
)
def list_assignments_endpoint(
    staff_profile_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> list[StaffServiceAssignmentResponse]:
    """List all service assignments for a staff profile.

    All roles can read assignments in their salon.
    Returns 404 if profile doesn't belong to salon.
    """
    # Verify profile exists in salon
    _get_tenant_profile_or_404(tenant, staff_profile_id)

    assignments = list_staff_service_assignments(
        tenant.db,
        staff_profile_id,
        tenant.salon.id,
    )
    return [StaffServiceAssignmentResponse.model_validate(a) for a in assignments]


@router.delete(
    "/salons/{salon_id}/staff-profiles/{staff_profile_id}/services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_assignment_endpoint(
    staff_profile_id: UUID,
    service_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> None:
    """Remove a service assignment from a staff profile.

    Only Owner/Manager can delete assignments.
    Returns 404 if assignment not found.
    """
    _require_assignment_mutation_permission(tenant)
    assignment = _get_tenant_assignment_or_404(tenant, staff_profile_id, service_id)

    delete_staff_service_assignment(tenant.db, assignment)
    tenant.db.commit()
