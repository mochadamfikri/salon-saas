"""Tenant-scoped Appointment API endpoints."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.tenant import TenantContext, get_tenant_context
from app.models import Appointment
from app.schemas.appointment import (
    AppointmentCreateRequest,
    AppointmentRescheduleRequest,
    AppointmentResponse,
)
from app.services.appointment import (
    AppointmentCapabilityError,
    AppointmentOverlapError,
    AppointmentTenantInvariantError,
    InvalidStateTransitionError,
    TerminalStateError,
    change_appointment_status,
    create_appointment,
    get_appointment,
    list_appointments,
    reschedule_appointment,
)

router = APIRouter(tags=["appointments"])


def _get_tenant_appointment_or_404(tenant: TenantContext, appointment_id: UUID) -> Appointment:
    """Load one appointment only when it belongs to the current tenant."""
    appointment = get_appointment(tenant.db, appointment_id, tenant.salon.id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return appointment


# ============================================================================
# Appointment CRUD Endpoints
# ============================================================================


@router.post(
    "/salons/{salon_id}/appointments",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_appointment_endpoint(
    payload: AppointmentCreateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AppointmentResponse:
    """Create a new appointment with capability, availability, and conflict validation.

    Owner/Manager/Staff may create appointments for their salon.
    """
    try:
        appointment = create_appointment(
            db=tenant.db,
            salon_id=tenant.salon.id,
            customer_id=payload.customer_id,
            service_id=payload.service_id,
            staff_profile_id=payload.staff_profile_id,
            starts_at=payload.starts_at,
            timezone_name=payload.timezone,
            notes=payload.notes,
        )
    except AppointmentTenantInvariantError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None
    except AppointmentCapabilityError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from None
    except AppointmentOverlapError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from None

    tenant.db.commit()
    return AppointmentResponse.model_validate(appointment)


@router.get("/salons/{salon_id}/appointments", response_model=list[AppointmentResponse])
def list_appointments_endpoint(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    starts_at_gte: Annotated[datetime | None, Query()] = None,
    starts_at_lte: Annotated[datetime | None, Query()] = None,
    staff_profile_id: Annotated[UUID | None, Query()] = None,
    customer_id: Annotated[UUID | None, Query()] = None,
    service_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[
        Literal["scheduled", "confirmed", "completed", "cancelled", "no_show"] | None,
        Query(alias="status"),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AppointmentResponse]:
    """List appointments with filtering and pagination.

    Owner/Manager/Staff may list appointments in their salon.
    Filters: date range, staff, customer, service, status.
    """
    appointments = list_appointments(
        db=tenant.db,
        salon_id=tenant.salon.id,
        starts_at_gte=starts_at_gte,
        starts_at_lte=starts_at_lte,
        staff_profile_id=staff_profile_id,
        customer_id=customer_id,
        service_id=service_id,
        appointment_status=status,
        offset=offset,
        limit=limit,
    )
    return [AppointmentResponse.model_validate(appt) for appt in appointments]


@router.get("/salons/{salon_id}/appointments/{appointment_id}", response_model=AppointmentResponse)
def get_appointment_endpoint(
    appointment_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AppointmentResponse:
    """Get an appointment belonging to the current tenant."""
    return AppointmentResponse.model_validate(
        _get_tenant_appointment_or_404(tenant, appointment_id)
    )


@router.patch(
    "/salons/{salon_id}/appointments/{appointment_id}", response_model=AppointmentResponse
)
def reschedule_appointment_endpoint(
    appointment_id: UUID,
    payload: AppointmentRescheduleRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AppointmentResponse:
    """Reschedule a non-terminal appointment with validation and conflict checking.

    Owner/Manager/Staff may reschedule appointments in their salon.
    Terminal states (completed, cancelled, no_show) cannot be rescheduled.
    """
    appointment = _get_tenant_appointment_or_404(tenant, appointment_id)

    if (payload.starts_at is None) != (payload.timezone is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="starts_at and timezone must be supplied together",
        )

    try:
        if payload.starts_at is not None and payload.timezone is not None:
            updated = reschedule_appointment(
                db=tenant.db,
                appointment=appointment,
                starts_at=payload.starts_at,
                timezone_name=payload.timezone,
            )
        else:
            updated = appointment
        if "notes" in payload.model_fields_set:
            updated.notes = payload.notes  # type: ignore[assignment]
            tenant.db.flush()
            tenant.db.refresh(updated)
    except TerminalStateError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from None
    except AppointmentTenantInvariantError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None
    except AppointmentCapabilityError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from None
    except AppointmentOverlapError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from None

    tenant.db.commit()
    return AppointmentResponse.model_validate(updated)


# ============================================================================
# Appointment Status Action Endpoints
# ============================================================================


@router.post(
    "/salons/{salon_id}/appointments/{appointment_id}/confirm",
    response_model=AppointmentResponse,
)
def confirm_appointment_endpoint(
    appointment_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AppointmentResponse:
    """Confirm a scheduled appointment.

    Owner/Manager/Staff may confirm appointments in their salon.
    Idempotent: confirming an already confirmed appointment succeeds.
    """
    appointment = _get_tenant_appointment_or_404(tenant, appointment_id)

    try:
        updated = change_appointment_status(tenant.db, appointment, "confirmed")
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from None

    tenant.db.commit()
    return AppointmentResponse.model_validate(updated)


@router.post(
    "/salons/{salon_id}/appointments/{appointment_id}/complete",
    response_model=AppointmentResponse,
)
def complete_appointment_endpoint(
    appointment_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AppointmentResponse:
    """Mark an appointment as completed.

    Owner/Manager/Staff may complete appointments in their salon.
    Idempotent: completing an already completed appointment succeeds.
    """
    appointment = _get_tenant_appointment_or_404(tenant, appointment_id)

    try:
        updated = change_appointment_status(tenant.db, appointment, "completed")
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from None

    tenant.db.commit()
    return AppointmentResponse.model_validate(updated)


@router.post(
    "/salons/{salon_id}/appointments/{appointment_id}/cancel",
    response_model=AppointmentResponse,
)
def cancel_appointment_endpoint(
    appointment_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AppointmentResponse:
    """Cancel an appointment.

    Owner/Manager/Staff may cancel appointments in their salon.
    Idempotent: cancelling an already cancelled appointment succeeds.
    """
    appointment = _get_tenant_appointment_or_404(tenant, appointment_id)

    try:
        updated = change_appointment_status(tenant.db, appointment, "cancelled")
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from None

    tenant.db.commit()
    return AppointmentResponse.model_validate(updated)


@router.post(
    "/salons/{salon_id}/appointments/{appointment_id}/no-show",
    response_model=AppointmentResponse,
)
def no_show_appointment_endpoint(
    appointment_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AppointmentResponse:
    """Mark an appointment as no-show.

    Owner/Manager/Staff may mark appointments as no-show in their salon.
    Idempotent: marking an already no-show appointment succeeds.
    """
    appointment = _get_tenant_appointment_or_404(tenant, appointment_id)

    try:
        updated = change_appointment_status(tenant.db, appointment, "no_show")
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from None

    tenant.db.commit()
    return AppointmentResponse.model_validate(updated)
