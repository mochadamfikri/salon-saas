"""Phase 3-B Appointment capability, availability, and conflict engine tests."""

import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

import pytest
from app.models import (
    Salon,
    SalonCustomer,
    SalonMembership,
    SalonService,
    StaffProfile,
    StaffServiceAssignment,
    StaffWeeklyAvailability,
    User,
)
from app.services.appointment import (
    AppointmentOverlapError,
    ServiceNotActiveError,
    StaffNotAvailableError,
    StaffNotBookableError,
    StaffServiceAssignmentError,
    create_appointment,
    find_overlapping_appointment,
    validate_appointment_availability,
    validate_appointment_capability,
    validate_appointment_conflict,
)
from sqlalchemy.orm import Session

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def p3b_full_context(db_session: Session) -> dict:
    """Create Phase 1+2+3 fixture with availability slots for P3-B tests."""
    unique_suffix = uuid.uuid4().hex[:8]

    # Phase 1: Users, Salon, Memberships
    owner = User(
        id=uuid.uuid4(),
        email=f"owner_{unique_suffix}@example.com",
        password_hash="hash",
    )
    staff_user = User(
        id=uuid.uuid4(),
        email=f"staff_{unique_suffix}@example.com",
        password_hash="hash",
    )
    db_session.add_all([owner, staff_user])
    db_session.flush()

    salon = Salon(
        id=uuid.uuid4(),
        name="Test Salon",
        slug=f"test-salon-{unique_suffix}",
        created_by_user_id=owner.id,
        status="active",
    )
    db_session.add(salon)
    db_session.flush()

    owner_membership = SalonMembership(
        id=uuid.uuid4(),
        salon_id=salon.id,
        user_id=owner.id,
        role="owner",
        status="active",
    )
    staff_membership = SalonMembership(
        id=uuid.uuid4(),
        salon_id=salon.id,
        user_id=staff_user.id,
        role="staff",
        status="active",
    )
    db_session.add_all([owner_membership, staff_membership])
    db_session.flush()

    # Phase 2: Service, Staff Profile, Assignment
    service = SalonService(
        id=uuid.uuid4(),
        salon_id=salon.id,
        name="Haircut",
        duration_minutes=30,
        price_amount=Decimal("150000"),
        currency="IDR",
        is_active=True,
    )
    db_session.add(service)
    db_session.flush()

    staff_profile = StaffProfile(
        id=uuid.uuid4(),
        membership_id=staff_membership.id,
        display_name="Jane Stylist",
        is_bookable=True,
    )
    db_session.add(staff_profile)
    db_session.flush()

    assignment = StaffServiceAssignment(
        id=uuid.uuid4(),
        staff_profile_id=staff_profile.id,
        salon_service_id=service.id,
    )
    db_session.add(assignment)
    db_session.flush()

    # Phase 2: Weekly Availability (Monday 09:00-17:00 in Asia/Jakarta)
    availability = StaffWeeklyAvailability(
        id=uuid.uuid4(),
        staff_profile_id=staff_profile.id,
        day_of_week=0,  # Monday
        start_time=time(9, 0),
        end_time=time(17, 0),
        is_available=True,
    )
    db_session.add(availability)
    db_session.flush()

    customer = SalonCustomer(
        id=uuid.uuid4(),
        salon_id=salon.id,
        full_name="John Customer",
        email=f"customer_{unique_suffix}@example.com",
        phone="08123456789",
    )
    db_session.add(customer)
    db_session.flush()

    return {
        "salon": salon,
        "owner": owner,
        "staff_user": staff_user,
        "owner_membership": owner_membership,
        "staff_membership": staff_membership,
        "service": service,
        "staff_profile": staff_profile,
        "assignment": assignment,
        "availability": availability,
        "customer": customer,
    }


# ============================================================================
# Service Activation Tests
# ============================================================================


def test_inactive_service_rejected(db_session: Session, p3b_full_context: dict):
    """Verify inactive service cannot be booked."""
    ctx = p3b_full_context
    ctx["service"].is_active = False
    db_session.flush()

    with pytest.raises(ServiceNotActiveError, match="Service is not active"):
        validate_appointment_capability(
            db=db_session,
            service=ctx["service"],
            staff_profile=ctx["staff_profile"],
        )


def test_active_service_accepted(db_session: Session, p3b_full_context: dict):
    """Verify active service passes capability check."""
    ctx = p3b_full_context
    validate_appointment_capability(
        db=db_session,
        service=ctx["service"],
        staff_profile=ctx["staff_profile"],
    )


# ============================================================================
# Staff Bookability Tests
# ============================================================================


def test_non_bookable_staff_rejected(db_session: Session, p3b_full_context: dict):
    """Verify staff profile with is_bookable=False cannot be booked."""
    ctx = p3b_full_context
    ctx["staff_profile"].is_bookable = False
    db_session.flush()

    with pytest.raises(StaffNotBookableError, match="Staff profile is not bookable"):
        validate_appointment_capability(
            db=db_session,
            service=ctx["service"],
            staff_profile=ctx["staff_profile"],
        )


def test_bookable_staff_accepted(db_session: Session, p3b_full_context: dict):
    """Verify bookable staff passes capability check."""
    ctx = p3b_full_context
    validate_appointment_capability(
        db=db_session,
        service=ctx["service"],
        staff_profile=ctx["staff_profile"],
    )


# ============================================================================
# Staff-Service Assignment Tests
# ============================================================================


def test_staff_without_service_assignment_rejected(db_session: Session, p3b_full_context: dict):
    """Verify staff must be assigned to the service."""
    ctx = p3b_full_context

    # Create another service without assignment
    other_service = SalonService(
        id=uuid.uuid4(),
        salon_id=ctx["salon"].id,
        name="Facial",
        duration_minutes=60,
        price_amount=Decimal("200000"),
        currency="IDR",
        is_active=True,
    )
    db_session.add(other_service)
    db_session.flush()

    with pytest.raises(
        StaffServiceAssignmentError, match="Staff profile is not assigned to this service"
    ):
        validate_appointment_capability(
            db=db_session,
            service=other_service,
            staff_profile=ctx["staff_profile"],
        )


def test_staff_with_service_assignment_accepted(db_session: Session, p3b_full_context: dict):
    """Verify assigned staff passes capability check."""
    ctx = p3b_full_context
    validate_appointment_capability(
        db=db_session,
        service=ctx["service"],
        staff_profile=ctx["staff_profile"],
    )


# ============================================================================
# Weekly Availability Validation Tests
# ============================================================================


def test_appointment_within_weekly_availability_accepted(
    db_session: Session, p3b_full_context: dict
):
    """Verify appointment within weekly slot is accepted."""
    ctx = p3b_full_context
    # Monday 2026-10-05 03:00-03:30 UTC (10:00-10:30 WIB/Jakarta, within 09:00-17:00)
    starts_at = datetime(2026, 10, 5, 3, 0, tzinfo=UTC)
    ends_at = starts_at + timedelta(minutes=30)

    validate_appointment_availability(
        db=db_session,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at,
        ends_at=ends_at,
        timezone_name="Asia/Jakarta",
    )


def test_appointment_outside_weekly_availability_rejected(
    db_session: Session, p3b_full_context: dict
):
    """Verify appointment outside weekly slot is rejected."""
    ctx = p3b_full_context
    # Monday 2026-10-05 23:00 UTC (Tuesday 06:00 WIB, outside Monday 09:00-17:00)
    starts_at = datetime(2026, 10, 5, 23, 0, tzinfo=UTC)
    ends_at = starts_at + timedelta(minutes=30)

    with pytest.raises(StaffNotAvailableError, match="not available for the requested time"):
        validate_appointment_availability(
            db=db_session,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=starts_at,
            ends_at=ends_at,
            timezone_name="Asia/Jakarta",
        )


def test_appointment_before_availability_start_rejected(
    db_session: Session, p3b_full_context: dict
):
    """Verify appointment starting before availability is rejected."""
    ctx = p3b_full_context
    # Monday 2026-10-05 01:00 UTC (08:00 WIB, before 09:00)
    starts_at = datetime(2026, 10, 5, 1, 0, tzinfo=UTC)
    ends_at = starts_at + timedelta(minutes=30)

    with pytest.raises(StaffNotAvailableError):
        validate_appointment_availability(
            db=db_session,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=starts_at,
            ends_at=ends_at,
            timezone_name="Asia/Jakarta",
        )


def test_appointment_after_availability_end_rejected(db_session: Session, p3b_full_context: dict):
    """Verify appointment ending after availability is rejected."""
    ctx = p3b_full_context
    # Monday 2026-10-05 10:00 UTC (17:00 WIB) for 60min service ends at 18:00 (past 17:00)
    starts_at = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
    ends_at = starts_at + timedelta(minutes=60)

    with pytest.raises(StaffNotAvailableError):
        validate_appointment_availability(
            db=db_session,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=starts_at,
            ends_at=ends_at,
            timezone_name="Asia/Jakarta",
        )


def test_appointment_crossing_midnight_rejected(db_session: Session, p3b_full_context: dict):
    """Verify appointment crossing local midnight is rejected."""
    ctx = p3b_full_context
    # Monday 2026-10-05 16:00 UTC (23:00 WIB) for 2-hour service crosses to Tuesday
    starts_at = datetime(2026, 10, 5, 16, 0, tzinfo=UTC)
    ends_at = starts_at + timedelta(minutes=120)

    with pytest.raises(StaffNotAvailableError, match="fit within one local availability day"):
        validate_appointment_availability(
            db=db_session,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=starts_at,
            ends_at=ends_at,
            timezone_name="Asia/Jakarta",
        )


def test_disabled_availability_slot_rejected(db_session: Session, p3b_full_context: dict):
    """Verify disabled availability slot is not bookable."""
    ctx = p3b_full_context
    ctx["availability"].is_available = False
    db_session.flush()

    starts_at = datetime(2026, 10, 5, 3, 0, tzinfo=UTC)
    ends_at = starts_at + timedelta(minutes=30)

    with pytest.raises(StaffNotAvailableError):
        validate_appointment_availability(
            db=db_session,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=starts_at,
            ends_at=ends_at,
            timezone_name="Asia/Jakarta",
        )


def test_appointment_on_day_without_availability_rejected(
    db_session: Session, p3b_full_context: dict
):
    """Verify appointment on day with no availability slot is rejected."""
    ctx = p3b_full_context
    # Tuesday 2026-10-06 (no availability slot defined)
    starts_at = datetime(2026, 10, 6, 3, 0, tzinfo=UTC)
    ends_at = starts_at + timedelta(minutes=30)

    with pytest.raises(StaffNotAvailableError):
        validate_appointment_availability(
            db=db_session,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=starts_at,
            ends_at=ends_at,
            timezone_name="Asia/Jakarta",
        )


# ============================================================================
# Overlap and Conflict Detection Tests
# ============================================================================


def test_overlapping_appointment_rejected(db_session: Session, p3b_full_context: dict):
    """Verify overlapping appointments are rejected."""
    ctx = p3b_full_context
    # Create first appointment
    starts_at_1 = datetime(2026, 10, 5, 3, 0, tzinfo=UTC)
    _ = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at_1,
        timezone_name="Asia/Jakarta",
    )
    db_session.commit()

    # Attempt overlapping appointment
    starts_at_2 = starts_at_1 + timedelta(minutes=15)
    with pytest.raises(AppointmentOverlapError, match="overlapping appointment"):
        create_appointment(
            db=db_session,
            salon_id=ctx["salon"].id,
            customer_id=ctx["customer"].id,
            service_id=ctx["service"].id,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=starts_at_2,
            timezone_name="Asia/Jakarta",
        )


def test_adjacent_appointments_allowed(db_session: Session, p3b_full_context: dict):
    """Verify adjacent appointments (no overlap) are allowed."""
    ctx = p3b_full_context
    starts_at_1 = datetime(2026, 10, 5, 3, 0, tzinfo=UTC)
    appointment1 = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at_1,
        timezone_name="Asia/Jakarta",
    )
    db_session.commit()

    # Adjacent appointment (starts when first ends)
    starts_at_2 = appointment1.ends_at
    appointment2 = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at_2,
        timezone_name="Asia/Jakarta",
    )
    db_session.commit()

    assert appointment2.starts_at == appointment1.ends_at


def test_cancelled_appointment_does_not_block(db_session: Session, p3b_full_context: dict):
    """Verify cancelled appointments do not block new bookings."""
    ctx = p3b_full_context
    starts_at_1 = datetime(2026, 10, 5, 3, 0, tzinfo=UTC)
    appointment1 = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at_1,
        timezone_name="Asia/Jakarta",
    )
    appointment1.status = "cancelled"
    db_session.commit()

    # Overlapping slot should now be available
    starts_at_2 = starts_at_1 + timedelta(minutes=15)
    appointment2 = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at_2,
        timezone_name="Asia/Jakarta",
    )
    db_session.commit()

    assert appointment2 is not None


def test_overlap_detection_predicate(db_session: Session, p3b_full_context: dict):
    """Verify overlap detection uses canonical predicate.

    Predicate: new_start < existing_end AND new_end > existing_start.
    """
    ctx = p3b_full_context
    # Existing: 10:00-10:30
    existing_start = datetime(2026, 10, 5, 3, 0, tzinfo=UTC)
    _ = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=existing_start,
        timezone_name="Asia/Jakarta",
    )
    db_session.commit()

    # Case 1: New 10:15-10:45 (overlaps)
    new_start_1 = existing_start + timedelta(minutes=15)
    new_end_1 = new_start_1 + timedelta(minutes=30)
    overlapping_1 = find_overlapping_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=new_start_1,
        ends_at=new_end_1,
    )
    assert overlapping_1 is not None

    # Case 2: New 09:30-10:15 (overlaps)
    new_start_2 = existing_start - timedelta(minutes=30)
    new_end_2 = existing_start + timedelta(minutes=15)
    overlapping_2 = find_overlapping_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=new_start_2,
        ends_at=new_end_2,
    )
    assert overlapping_2 is not None

    # Case 3: New 09:00-09:30 (adjacent, no overlap)
    new_start_3 = existing_start - timedelta(minutes=60)
    new_end_3 = existing_start
    overlapping_3 = find_overlapping_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=new_start_3,
        ends_at=new_end_3,
    )
    assert overlapping_3 is None


def test_conflict_validation_with_exclude(db_session: Session, p3b_full_context: dict):
    """Verify exclude_appointment_id allows updating the same appointment."""
    ctx = p3b_full_context
    starts_at = datetime(2026, 10, 5, 3, 0, tzinfo=UTC)
    appointment = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at,
        timezone_name="Asia/Jakarta",
    )
    db_session.commit()

    # Validate same slot with exclusion (should pass)
    validate_appointment_conflict(
        db=db_session,
        salon_id=ctx["salon"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at,
        ends_at=appointment.ends_at,
        exclude_appointment_id=appointment.id,
    )


# ============================================================================
# Integration: Full Booking Flow
# ============================================================================


def test_create_appointment_with_all_validations_success(
    db_session: Session, p3b_full_context: dict
):
    """Verify appointment creation succeeds with all P3-B validations."""
    ctx = p3b_full_context
    starts_at = datetime(2026, 10, 5, 3, 0, tzinfo=UTC)

    appointment = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at,
        timezone_name="Asia/Jakarta",
    )

    assert appointment.id is not None
    assert appointment.status == "scheduled"


def test_create_appointment_with_inactive_service_rejected(
    db_session: Session, p3b_full_context: dict
):
    """Verify inactive service blocks appointment creation."""
    ctx = p3b_full_context
    ctx["service"].is_active = False
    db_session.flush()

    starts_at = datetime(2026, 10, 5, 3, 0, tzinfo=UTC)
    with pytest.raises(ServiceNotActiveError):
        create_appointment(
            db=db_session,
            salon_id=ctx["salon"].id,
            customer_id=ctx["customer"].id,
            service_id=ctx["service"].id,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=starts_at,
            timezone_name="Asia/Jakarta",
        )


def test_create_appointment_with_non_bookable_staff_rejected(
    db_session: Session, p3b_full_context: dict
):
    """Verify non-bookable staff blocks appointment creation."""
    ctx = p3b_full_context
    ctx["staff_profile"].is_bookable = False
    db_session.flush()

    starts_at = datetime(2026, 10, 5, 3, 0, tzinfo=UTC)
    with pytest.raises(StaffNotBookableError):
        create_appointment(
            db=db_session,
            salon_id=ctx["salon"].id,
            customer_id=ctx["customer"].id,
            service_id=ctx["service"].id,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=starts_at,
            timezone_name="Asia/Jakarta",
        )


def test_create_appointment_without_availability_rejected(
    db_session: Session, p3b_full_context: dict
):
    """Verify missing availability blocks appointment creation."""
    ctx = p3b_full_context
    # Tuesday (no availability defined)
    starts_at = datetime(2026, 10, 6, 3, 0, tzinfo=UTC)

    with pytest.raises(StaffNotAvailableError):
        create_appointment(
            db=db_session,
            salon_id=ctx["salon"].id,
            customer_id=ctx["customer"].id,
            service_id=ctx["service"].id,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=starts_at,
            timezone_name="Asia/Jakarta",
        )


# ============================================================================
# Timezone Interpretation Tests
# ============================================================================


def test_availability_interpreted_in_appointment_timezone(
    db_session: Session, p3b_full_context: dict
):
    """Verify availability is interpreted in the appointment's IANA timezone."""
    ctx = p3b_full_context
    # Monday 2026-10-05 02:00 UTC = 10:00 Asia/Jakarta (within 09:00-17:00)
    starts_at = datetime(2026, 10, 5, 2, 0, tzinfo=UTC)
    ends_at = starts_at + timedelta(minutes=30)

    validate_appointment_availability(
        db=db_session,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at,
        ends_at=ends_at,
        timezone_name="Asia/Jakarta",
    )


def test_same_utc_instant_different_timezone_fails(db_session: Session, p3b_full_context: dict):
    """Verify same UTC instant maps to different local time in different timezone."""
    ctx = p3b_full_context
    # Monday 2026-10-05 02:00 UTC = 10:00 Asia/Jakarta (OK)
    # But 02:00 UTC = 22:00 America/New_York Sunday (outside Monday 09:00-17:00)
    starts_at = datetime(2026, 10, 5, 2, 0, tzinfo=UTC)
    ends_at = starts_at + timedelta(minutes=30)

    # Works for Asia/Jakarta
    validate_appointment_availability(
        db=db_session,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at,
        ends_at=ends_at,
        timezone_name="Asia/Jakarta",
    )

    # Fails for America/New_York (wrong day and time)
    with pytest.raises(StaffNotAvailableError):
        validate_appointment_availability(
            db=db_session,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=starts_at,
            ends_at=ends_at,
            timezone_name="America/New_York",
        )
