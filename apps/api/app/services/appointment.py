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
    StaffServiceAssignment,
    StaffWeeklyAvailability,
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


class AppointmentCapabilityError(ValueError):
    """Base exception for capability and availability validation failures."""

    pass


class ServiceNotActiveError(AppointmentCapabilityError):
    """Raised when attempting to book an inactive service."""

    pass


class StaffNotBookableError(AppointmentCapabilityError):
    """Raised when attempting to book a staff member not marked as bookable."""

    pass


class StaffServiceAssignmentError(AppointmentCapabilityError):
    """Raised when staff member is not assigned to the requested service."""

    pass


class StaffNotAvailableError(AppointmentCapabilityError):
    """Raised when staff member has no availability for the requested time slot."""

    pass


class AppointmentOverlapError(ValueError):
    """Raised when an appointment would overlap with an existing appointment."""

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


# ============================================================================
# Booking Capability, Availability, and Conflict Validation
# ============================================================================


def _acquire_staff_booking_lock(db: Session, staff_profile_id: UUID) -> None:
    """Serialize booking conflict checks for one staff profile within a transaction.

    PostgreSQL advisory transaction locks close the check-then-insert race without
    introducing a schema-specific exclusion constraint. The lock is released when
    the enclosing transaction commits or rolls back.
    """
    lock_key = int.from_bytes(staff_profile_id.bytes[:8], byteorder="big", signed=True)
    db.connection().exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (lock_key,))


def validate_appointment_capability(
    db: Session,
    service: SalonService,
    staff_profile: StaffProfile,
) -> None:
    """Validate that the selected active service can be booked by the staff profile."""
    if not service.is_active:
        raise ServiceNotActiveError("Service is not active")

    if not staff_profile.is_bookable:
        raise StaffNotBookableError("Staff profile is not bookable")

    assignment_exists = (
        db.query(StaffServiceAssignment.id)
        .filter(
            StaffServiceAssignment.staff_profile_id == staff_profile.id,
            StaffServiceAssignment.salon_service_id == service.id,
        )
        .first()
        is not None
    )
    if not assignment_exists:
        raise StaffServiceAssignmentError("Staff profile is not assigned to this service")


def validate_appointment_availability(
    db: Session,
    staff_profile_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    timezone_name: str,
) -> None:
    """Require a single enabled weekly slot to contain the local appointment interval.

    Weekly availability is interpreted in the appointment's IANA timezone. A booking
    that crosses a local-date boundary is unavailable because Phase 2 weekly slots do
    not span midnight.
    """
    timezone = ZoneInfo(timezone_name)
    local_start = starts_at.astimezone(timezone)
    local_end = ends_at.astimezone(timezone)
    if local_start.date() != local_end.date():
        raise StaffNotAvailableError("Appointment must fit within one local availability day")

    start_time = local_start.timetz().replace(tzinfo=None)
    end_time = local_end.timetz().replace(tzinfo=None)
    availability_exists = (
        db.query(StaffWeeklyAvailability.id)
        .filter(
            StaffWeeklyAvailability.staff_profile_id == staff_profile_id,
            StaffWeeklyAvailability.day_of_week == local_start.weekday(),
            StaffWeeklyAvailability.is_available.is_(True),
            StaffWeeklyAvailability.start_time <= start_time,
            StaffWeeklyAvailability.end_time >= end_time,
        )
        .first()
        is not None
    )
    if not availability_exists:
        raise StaffNotAvailableError("Staff profile is not available for the requested time")


def find_overlapping_appointment(
    db: Session,
    salon_id: UUID,
    staff_profile_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_appointment_id: UUID | None = None,
) -> Appointment | None:
    """Return the first blocking staff appointment using the canonical overlap predicate."""
    query = db.query(Appointment).filter(
        Appointment.salon_id == salon_id,
        Appointment.staff_profile_id == staff_profile_id,
        Appointment.status != "cancelled",
        starts_at < Appointment.ends_at,
        ends_at > Appointment.starts_at,
    )
    if exclude_appointment_id is not None:
        query = query.filter(Appointment.id != exclude_appointment_id)
    return query.first()


def validate_appointment_conflict(
    db: Session,
    salon_id: UUID,
    staff_profile_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_appointment_id: UUID | None = None,
) -> None:
    """Raise a deterministic error when a staff appointment overlaps another booking."""
    overlapping = find_overlapping_appointment(
        db=db,
        salon_id=salon_id,
        staff_profile_id=staff_profile_id,
        starts_at=starts_at,
        ends_at=ends_at,
        exclude_appointment_id=exclude_appointment_id,
    )
    if overlapping is not None:
        raise AppointmentOverlapError("Staff profile already has an overlapping appointment")


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
    """Create an appointment after tenant, capability, availability, and conflict checks.

    Appointment duration and service metadata are snapshotted from the active service.
    A per-staff PostgreSQL transaction advisory lock serializes the conflict check and
    insert, preventing overlapping concurrent bookings when callers commit normally.

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
    _, service, staff_profile = validate_appointment_tenant_invariants(
        db=db,
        salon_id=salon_id,
        customer_id=customer_id,
        service_id=service_id,
        staff_profile_id=staff_profile_id,
    )

    # Compute ends_at from service duration snapshot
    duration = service.duration_minutes
    ends_at = starts_at + timedelta(minutes=duration)

    # P3-B: Validate capability (service active, staff bookable, assignment exists)
    validate_appointment_capability(db=db, service=service, staff_profile=staff_profile)

    # P3-B: Validate weekly availability
    validate_appointment_availability(
        db=db,
        staff_profile_id=staff_profile_id,
        starts_at=starts_at,
        ends_at=ends_at,
        timezone_name=valid_tz,
    )

    # P3-B: Acquire advisory lock and check overlap with race-safe serialization
    _acquire_staff_booking_lock(db=db, staff_profile_id=staff_profile_id)
    validate_appointment_conflict(
        db=db,
        salon_id=salon_id,
        staff_profile_id=staff_profile_id,
        starts_at=starts_at,
        ends_at=ends_at,
    )

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
