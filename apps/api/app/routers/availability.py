"""Tenant-scoped Staff Weekly Availability API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.core.tenant import TenantContext, get_tenant_context
from app.models import StaffProfile, StaffWeeklyAvailability
from app.schemas.availability import (
    AvailabilityCreateRequest,
    AvailabilityResponse,
    AvailabilityUpdateRequest,
)
from app.services.availability import (
    create_availability,
    delete_availability,
    get_availability,
    list_availability,
    update_availability,
)
from app.services.staff_profile import get_staff_profile

router = APIRouter(tags=["staff-availability"])


def _is_expected_duplicate_error(error: IntegrityError, constraint_name: str) -> bool:
    """Return whether an IntegrityError is the expected named UNIQUE constraint."""
    diagnostics = getattr(getattr(error, "orig", None), "diag", None)
    return getattr(diagnostics, "constraint_name", None) == constraint_name


def _require_availability_mutation_permission(
    tenant: TenantContext,
    profile: StaffProfile,
) -> None:
    """Require permission to mutate availability.

    Owner/Manager: can mutate any profile's availability in the salon.
    Staff: can only mutate their own profile's availability.
    """
    # Owner/Manager can mutate any profile
    if tenant.role in ("owner", "manager"):
        return

    # Staff can only mutate their own profile
    if profile.membership.user_id == tenant.user.id:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You can only manage your own availability",
    )


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


def _get_tenant_availability_or_404(
    tenant: TenantContext,
    availability_id: UUID,
) -> StaffWeeklyAvailability:
    """Load one availability slot only when it belongs to the current tenant."""
    availability = get_availability(tenant.db, availability_id, tenant.salon.id)
    if availability is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability not found",
        )
    return availability


# ============================================================================
# Staff Weekly Availability Endpoints
# ============================================================================


@router.post(
    "/salons/{salon_id}/staff-profiles/{staff_profile_id}/availability",
    response_model=AvailabilityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_availability_endpoint(
    staff_profile_id: UUID,
    payload: AvailabilityCreateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AvailabilityResponse:
    """Create a weekly availability slot for a staff profile.

    Owner/Manager: can create for any profile.
    Staff: can only create for their own profile.
    Rejects overlapping slots with 409.
    """
    profile = _get_tenant_profile_or_404(tenant, staff_profile_id)
    _require_availability_mutation_permission(tenant, profile)

    try:
        availability = create_availability(
            tenant.db,
            staff_profile_id=staff_profile_id,
            day_of_week=payload.day_of_week,
            start_time=payload.start_time,
            end_time=payload.end_time,
            salon_id=tenant.salon.id,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            ) from None
        if "overlap" in error_msg.lower():
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
        if _is_expected_duplicate_error(e, "uq_staff_weekly_availability_staff_day_start"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate availability slot (same start time)",
            ) from None
        raise

    try:
        tenant.db.commit()
    except IntegrityError as e:
        tenant.db.rollback()
        if _is_expected_duplicate_error(e, "uq_staff_weekly_availability_staff_day_start"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate availability slot (same start time)",
            ) from None
        raise

    return AvailabilityResponse.model_validate(availability)


@router.get(
    "/salons/{salon_id}/staff-profiles/{staff_profile_id}/availability",
    response_model=list[AvailabilityResponse],
)
def list_availability_endpoint(
    staff_profile_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> list[AvailabilityResponse]:
    """List all availability slots for a staff profile.

    All roles can read availability in their salon.
    Returns 404 if profile doesn't belong to salon.
    """
    # Verify profile exists in salon
    _get_tenant_profile_or_404(tenant, staff_profile_id)

    slots = list_availability(tenant.db, staff_profile_id, tenant.salon.id)
    return [AvailabilityResponse.model_validate(slot) for slot in slots]


@router.patch(
    "/salons/{salon_id}/staff-profiles/{staff_profile_id}/availability/{availability_id}",
    response_model=AvailabilityResponse,
)
def update_availability_endpoint(
    staff_profile_id: UUID,
    availability_id: UUID,
    payload: AvailabilityUpdateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AvailabilityResponse:
    """Update a weekly availability slot.

    Owner/Manager: can update any profile's availability.
    Staff: can only update their own profile's availability.
    Rejects overlapping slots with 409.
    """
    availability = _get_tenant_availability_or_404(tenant, availability_id)

    # Verify availability belongs to the specified profile
    if availability.staff_profile_id != staff_profile_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability not found",
        )

    profile = _get_tenant_profile_or_404(tenant, staff_profile_id)
    _require_availability_mutation_permission(tenant, profile)

    try:
        updated = update_availability(
            tenant.db,
            availability,
            **payload.model_dump(exclude_unset=True),
        )
    except ValueError as e:
        error_msg = str(e)
        if "overlap" in error_msg.lower():
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
        if _is_expected_duplicate_error(e, "uq_staff_weekly_availability_staff_day_start"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate availability slot (same start time)",
            ) from None
        raise

    try:
        tenant.db.commit()
    except IntegrityError as e:
        tenant.db.rollback()
        if _is_expected_duplicate_error(e, "uq_staff_weekly_availability_staff_day_start"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate availability slot (same start time)",
            ) from None
        raise

    return AvailabilityResponse.model_validate(updated)


@router.delete(
    "/salons/{salon_id}/staff-profiles/{staff_profile_id}/availability/{availability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_availability_endpoint(
    staff_profile_id: UUID,
    availability_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> None:
    """Delete a weekly availability slot.

    Owner/Manager: can delete any profile's availability.
    Staff: can only delete their own profile's availability.
    """
    availability = _get_tenant_availability_or_404(tenant, availability_id)

    # Verify availability belongs to the specified profile
    if availability.staff_profile_id != staff_profile_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Availability not found",
        )

    profile = _get_tenant_profile_or_404(tenant, staff_profile_id)
    _require_availability_mutation_permission(tenant, profile)

    delete_availability(tenant.db, availability)
    tenant.db.commit()
