"""Appointment lifecycle business logic and state transitions.

Phase 3-A provides domain model and lifecycle validator. Phase 3-B adds
availability/capability validation. Phase 3-C adds API routing.
"""

from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.models import (
    Appointment,
    SalonCustomer,
    SalonMembership,
    SalonService,
    StaffProfile,
)

# ============================================================================
# Exceptions
# ============================================================================


class AppointmentLifecycleError(ValueError):
    """Base exception for appointment lifecycle violations."""

    pass


class InvalidStateTransitionError(AppointmentLifecycleError):
    """Raised when an invalid status transition is attempted."""

    pass


class TerminalStateError(InvalidStateTransitionError):
    """Raised when attempting to transition from a terminal state."""

    pass


class AppointmentTenantInvariantError(ValueError):
    """Base exception for tenant invariant violations."""

    pass


class CrossTenantResourceError(AppointmentTenantInvariantError):
    """Raised when a resource does not belong to the salon context."""

    pass


# ============================================================================
# Lifecycle State Machine
# ============================================================================

# Terminal states that cannot transition to any other state
TERMINAL_STATES = {"completed", "cancelled", "no_show"}

# Valid state transitions
VALID_TRANSITIONS = {
    "scheduled": {"confirmed", "cancelled", "completed", "no_show"},
    "confirmed": {"completed", "cancelled", "no_show"},
    "completed": set(),
    "cancelled": set(),
    "no_show": set(),
}


def validate_status_transition(current_status: str, new_status: str) -> None:
    """Validate appointment status transition.

    Args:
        current_status: Current appointment status
        new_status: Requested new status

    Raises:
        TerminalStateError: If current status is a terminal state
        InvalidStateTransitionError: If transition is not allowed
    """
    if current_status == new_status:
        return  # Idempotent: same state is allowed

    if current_status in TERMINAL_STATES:
        raise TerminalStateError(f"Cannot transition from terminal state '{current_status}'")

    if new_status not in VALID_TRANSITIONS.get(current_status, set()):
        raise InvalidStateTransitionError(
            f"Invalid transition from '{current_status}' to '{new_status}'. "
            f"Allowed: {', '.join(sorted(VALID_TRANSITIONS.get(current_status, set())))}"
        )


def change_appointment_status(
    db: Session,
    appointment: Appointment,
    new_status: str,
) -> Appointment:
    """Change appointment status with lifecycle validation.

    Args:
        db: Database session
        appointment: Existing appointment
        new_status: Requested status

    Returns:
        Updated appointment

    Raises:
        InvalidStateTransitionError: If status transition is invalid
    """
    validate_status_transition(appointment.status, new_status)

    appointment.status = new_status
    db.flush()
    db.refresh(appointment)
    return appointment


# ============================================================================
# Invariant Validation & Snapshot Computation
# ============================================================================


def validate_iana_timezone(timezone_name: str) -> str:
    """Validate that a timezone string is a valid IANA timezone.

    Args:
        timezone_name: Timezone identifier (e.g., 'Asia/Jakarta', 'UTC')

    Returns:
        Validated timezone string

    Raises:
        ValueError: If timezone name is invalid
    """
    try:
        ZoneInfo(timezone_name)
        return timezone_name
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid IANA timezone: '{timezone_name}'") from exc


def validate_appointment_tenant_invariants(
    db: Session,
    salon_id: UUID,
    customer_id: UUID,
    service_id: UUID,
    staff_profile_id: UUID,
) -> tuple[SalonCustomer, SalonService, StaffProfile]:
    """Validate tenant boundaries for appointment resources.

    Verifies:
    1. Customer exists and belongs to salon
    2. Service exists and belongs to salon
    3. Staff profile exists and belongs to salon via membership

    Args:
        db: Database session
        salon_id: Current tenant salon UUID
        customer_id: Customer UUID
        service_id: Service UUID
        staff_profile_id: Staff profile UUID

    Returns:
        Tuple of (SalonCustomer, SalonService, StaffProfile)

    Raises:
        CrossTenantResourceError: If any resource belongs to another salon or is missing
    """
    # 1. Customer check
    customer = (
        db.query(SalonCustomer)
        .filter(
            SalonCustomer.id == customer_id,
            SalonCustomer.salon_id == salon_id,
        )
        .first()
    )
    if not customer:
        raise CrossTenantResourceError("Customer not found in this salon")

    # 2. Service check
    service = (
        db.query(SalonService)
        .filter(
            SalonService.id == service_id,
            SalonService.salon_id == salon_id,
        )
        .first()
    )
    if not service:
        raise CrossTenantResourceError("Service not found in this salon")

    # 3. Staff profile check
    profile = (
        db.query(StaffProfile)
        .join(SalonMembership, StaffProfile.membership_id == SalonMembership.id)
        .filter(
            StaffProfile.id == staff_profile_id,
            SalonMembership.salon_id == salon_id,
        )
        .first()
    )
    if not profile:
        raise CrossTenantResourceError("Staff profile not found in this salon")

    return customer, service, profile


def create_appointment(
    db: Session,
    salon_id: UUID,
    customer_id: UUID,
    service_id: UUID,
    staff_profile_id: UUID,
    starts_at: datetime,
    timezone_name: str,
    notes: str | None = None,
) -> Appointment:
    """Create an appointment record with snapshot capture and invariant validation.

    Note: Overlap and availability validation are handled in P3-B.
    This function validates tenant boundaries, takes snapshots, and enforces lifecycle.

    Args:
        db: Database session
        salon_id: Current tenant salon UUID
        customer_id: Target customer UUID
        service_id: Target service UUID
        staff_profile_id: Assigned staff profile UUID
        starts_at: Booking start datetime (timezone-aware)
        timezone_name: IANA timezone identifier
        notes: Optional customer/operational notes

    Returns:
        Created Appointment instance

    Raises:
        ValueError: If starts_at is not timezone-aware or timezone_name is invalid
        AppointmentTenantInvariantError: If any tenant invariant is violated
    """
    if starts_at.tzinfo is None:
        raise ValueError("starts_at must be timezone-aware")

    valid_tz = validate_iana_timezone(timezone_name)

    # Validate tenant invariants and retrieve entities
    _, service, _ = validate_appointment_tenant_invariants(
        db=db,
        salon_id=salon_id,
        customer_id=customer_id,
        service_id=service_id,
        staff_profile_id=staff_profile_id,
    )

    # Compute ends_at from service duration snapshot
    duration = service.duration_minutes
    ends_at = starts_at + timedelta(minutes=duration)

    appointment = Appointment(
        salon_id=salon_id,
        customer_id=customer_id,
        service_id=service_id,
        staff_profile_id=staff_profile_id,
        starts_at=starts_at,
        ends_at=ends_at,
        timezone=valid_tz,
        service_name_snapshot=service.name,
        duration_minutes_snapshot=duration,
        price_amount_snapshot=service.price_amount,
        currency_snapshot=service.currency,
        status="scheduled",
        notes=notes,
    )

    db.add(appointment)
    db.flush()
    db.refresh(appointment)
    return appointment

