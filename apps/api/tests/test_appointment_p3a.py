"""Phase 3 Appointment domain model and lifecycle state machine tests."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.models import (
    Salon,
    SalonCustomer,
    SalonMembership,
    SalonService,
    StaffProfile,
    StaffServiceAssignment,
    User,
)
from app.services.appointment import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    CrossTenantResourceError,
    InvalidStateTransitionError,
    TerminalStateError,
    change_appointment_status,
    create_appointment,
    get_appointment,
    list_appointments,
    validate_iana_timezone,
    validate_status_transition,
)
from sqlalchemy.orm import Session

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def phase3_test_context(db_session: Session) -> dict:
    """Create full Phase 1 + Phase 2 + customer fixture for Phase 3 tests."""
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

    # Phase 2: Service, Staff Profile, Customer
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
        "customer": customer,
    }


# ============================================================================
# Lifecycle State Machine Tests
# ============================================================================


def test_lifecycle_terminal_states_defined():
    """Verify terminal states are correctly defined."""
    assert TERMINAL_STATES == {"completed", "cancelled", "no_show"}


def test_lifecycle_valid_transitions_defined():
    """Verify all valid transitions are defined."""
    assert "scheduled" in VALID_TRANSITIONS
    assert "confirmed" in VALID_TRANSITIONS
    assert "completed" in VALID_TRANSITIONS
    assert "cancelled" in VALID_TRANSITIONS
    assert "no_show" in VALID_TRANSITIONS


def test_lifecycle_scheduled_to_confirmed():
    """Verify scheduled → confirmed is valid."""
    validate_status_transition("scheduled", "confirmed")


def test_lifecycle_scheduled_to_cancelled():
    """Verify scheduled → cancelled is valid."""
    validate_status_transition("scheduled", "cancelled")


def test_lifecycle_scheduled_to_completed():
    """Verify scheduled → completed is valid."""
    validate_status_transition("scheduled", "completed")


def test_lifecycle_scheduled_to_no_show():
    """Verify scheduled → no_show is valid."""
    validate_status_transition("scheduled", "no_show")


def test_lifecycle_confirmed_to_completed():
    """Verify confirmed → completed is valid."""
    validate_status_transition("confirmed", "completed")


def test_lifecycle_confirmed_to_cancelled():
    """Verify confirmed → cancelled is valid."""
    validate_status_transition("confirmed", "cancelled")


def test_lifecycle_confirmed_to_no_show():
    """Verify confirmed → no_show is valid."""
    validate_status_transition("confirmed", "no_show")


def test_lifecycle_terminal_state_cannot_transition():
    """Verify terminal states cannot transition."""
    with pytest.raises(TerminalStateError):
        validate_status_transition("completed", "cancelled")

    with pytest.raises(TerminalStateError):
        validate_status_transition("cancelled", "scheduled")

    with pytest.raises(TerminalStateError):
        validate_status_transition("no_show", "confirmed")


def test_lifecycle_invalid_transition_rejected():
    """Verify invalid transitions are rejected."""
    # confirmed cannot go back to scheduled
    with pytest.raises(InvalidStateTransitionError):
        validate_status_transition("confirmed", "scheduled")


def test_lifecycle_idempotent_transition_allowed():
    """Verify same-state transitions are allowed (idempotent)."""
    validate_status_transition("scheduled", "scheduled")
    validate_status_transition("confirmed", "confirmed")
    validate_status_transition("completed", "completed")


# ============================================================================
# IANA Timezone Validation Tests
# ============================================================================


def test_validate_iana_timezone_valid():
    """Verify valid IANA timezones are accepted."""
    assert validate_iana_timezone("UTC") == "UTC"
    assert validate_iana_timezone("Asia/Jakarta") == "Asia/Jakarta"
    assert validate_iana_timezone("America/New_York") == "America/New_York"


def test_validate_iana_timezone_invalid():
    """Verify invalid timezones are rejected."""
    with pytest.raises(ValueError, match="Invalid IANA timezone"):
        validate_iana_timezone("InvalidZone")

    with pytest.raises(ValueError, match="Invalid IANA timezone"):
        validate_iana_timezone("WIB")


# ============================================================================
# Appointment Creation Tests
# ============================================================================


def test_create_appointment_success(db_session: Session, phase3_test_context: dict):
    """Verify appointment creation with valid inputs."""
    ctx = phase3_test_context
    starts_at = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)

    appointment = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at,
        timezone_name="Asia/Jakarta",
        notes="First appointment",
    )

    assert appointment.id is not None
    assert appointment.salon_id == ctx["salon"].id
    assert appointment.customer_id == ctx["customer"].id
    assert appointment.service_id == ctx["service"].id
    assert appointment.staff_profile_id == ctx["staff_profile"].id
    assert appointment.starts_at == starts_at
    assert appointment.ends_at == starts_at + timedelta(minutes=30)
    assert appointment.timezone == "Asia/Jakarta"
    assert appointment.service_name_snapshot == "Haircut"
    assert appointment.duration_minutes_snapshot == 30
    assert appointment.price_amount_snapshot == Decimal("150000")
    assert appointment.currency_snapshot == "IDR"
    assert appointment.status == "scheduled"
    assert appointment.notes == "First appointment"


def test_create_appointment_naive_datetime_rejected(db_session: Session, phase3_test_context: dict):
    """Verify naive datetime is rejected."""
    ctx = phase3_test_context
    naive_dt = datetime(2026, 10, 15, 10, 0)

    with pytest.raises(ValueError, match="starts_at must be timezone-aware"):
        create_appointment(
            db=db_session,
            salon_id=ctx["salon"].id,
            customer_id=ctx["customer"].id,
            service_id=ctx["service"].id,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=naive_dt,
            timezone_name="Asia/Jakarta",
        )


def test_create_appointment_invalid_timezone(db_session: Session, phase3_test_context: dict):
    """Verify invalid timezone is rejected."""
    ctx = phase3_test_context
    starts_at = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="Invalid IANA timezone"):
        create_appointment(
            db=db_session,
            salon_id=ctx["salon"].id,
            customer_id=ctx["customer"].id,
            service_id=ctx["service"].id,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=starts_at,
            timezone_name="InvalidZone",
        )


def test_create_appointment_cross_tenant_customer_rejected(
    db_session: Session, phase3_test_context: dict
):
    """Verify cross-tenant customer is rejected."""
    ctx = phase3_test_context
    starts_at = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)

    # Create another salon and customer
    other_salon = Salon(
        id=uuid.uuid4(),
        name="Other Salon",
        slug=f"other-salon-{uuid.uuid4().hex[:8]}",
        created_by_user_id=ctx["owner"].id,
    )
    db_session.add(other_salon)
    db_session.flush()

    other_customer = SalonCustomer(
        id=uuid.uuid4(),
        salon_id=other_salon.id,
        full_name="Other Customer",
    )
    db_session.add(other_customer)
    db_session.flush()

    with pytest.raises(CrossTenantResourceError, match="Customer not found in this salon"):
        create_appointment(
            db=db_session,
            salon_id=ctx["salon"].id,
            customer_id=other_customer.id,
            service_id=ctx["service"].id,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=starts_at,
            timezone_name="Asia/Jakarta",
        )


def test_create_appointment_cross_tenant_service_rejected(
    db_session: Session, phase3_test_context: dict
):
    """Verify cross-tenant service is rejected."""
    ctx = phase3_test_context
    starts_at = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)

    # Create another salon and service
    other_salon = Salon(
        id=uuid.uuid4(),
        name="Other Salon",
        slug=f"other-salon-{uuid.uuid4().hex[:8]}",
        created_by_user_id=ctx["owner"].id,
    )
    db_session.add(other_salon)
    db_session.flush()

    other_service = SalonService(
        id=uuid.uuid4(),
        salon_id=other_salon.id,
        name="Other Service",
        duration_minutes=45,
        price_amount=Decimal("200000"),
        currency="IDR",
        is_active=True,
    )
    db_session.add(other_service)
    db_session.flush()

    with pytest.raises(CrossTenantResourceError, match="Service not found in this salon"):
        create_appointment(
            db=db_session,
            salon_id=ctx["salon"].id,
            customer_id=ctx["customer"].id,
            service_id=other_service.id,
            staff_profile_id=ctx["staff_profile"].id,
            starts_at=starts_at,
            timezone_name="Asia/Jakarta",
        )


def test_create_appointment_cross_tenant_staff_rejected(
    db_session: Session, phase3_test_context: dict
):
    """Verify cross-tenant staff profile is rejected."""
    ctx = phase3_test_context
    starts_at = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)

    # Create another salon, membership and staff profile
    other_salon = Salon(
        id=uuid.uuid4(),
        name="Other Salon",
        slug=f"other-salon-{uuid.uuid4().hex[:8]}",
        created_by_user_id=ctx["owner"].id,
    )
    db_session.add(other_salon)
    db_session.flush()

    other_membership = SalonMembership(
        id=uuid.uuid4(),
        salon_id=other_salon.id,
        user_id=ctx["staff_user"].id,
        role="staff",
        status="active",
    )
    db_session.add(other_membership)
    db_session.flush()

    other_staff_profile = StaffProfile(
        id=uuid.uuid4(),
        membership_id=other_membership.id,
        display_name="Other Stylist",
        is_bookable=True,
    )
    db_session.add(other_staff_profile)
    db_session.flush()

    with pytest.raises(CrossTenantResourceError, match="Staff profile not found in this salon"):
        create_appointment(
            db=db_session,
            salon_id=ctx["salon"].id,
            customer_id=ctx["customer"].id,
            service_id=ctx["service"].id,
            staff_profile_id=other_staff_profile.id,
            starts_at=starts_at,
            timezone_name="Asia/Jakarta",
        )


# ============================================================================
# Appointment Status Change Tests
# ============================================================================


def test_change_appointment_status_success(db_session: Session, phase3_test_context: dict):
    """Verify appointment status can be changed."""
    ctx = phase3_test_context
    starts_at = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)

    appointment = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at,
        timezone_name="Asia/Jakarta",
    )

    assert appointment.status == "scheduled"

    updated = change_appointment_status(db_session, appointment, "confirmed")
    assert updated.status == "confirmed"


def test_change_appointment_status_terminal_state_rejected(
    db_session: Session, phase3_test_context: dict
):
    """Verify terminal states cannot be changed."""
    ctx = phase3_test_context
    starts_at = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)

    appointment = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at,
        timezone_name="Asia/Jakarta",
    )

    # Move to terminal state
    change_appointment_status(db_session, appointment, "completed")
    assert appointment.status == "completed"

    # Attempt to change from terminal state
    with pytest.raises(TerminalStateError):
        change_appointment_status(db_session, appointment, "cancelled")


# ============================================================================
# Appointment Read Tests
# ============================================================================


def test_get_appointment_success(db_session: Session, phase3_test_context: dict):
    """Verify appointment can be retrieved."""
    ctx = phase3_test_context
    starts_at = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)

    appointment = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at,
        timezone_name="Asia/Jakarta",
    )

    retrieved = get_appointment(db_session, appointment.id, ctx["salon"].id)
    assert retrieved is not None
    assert retrieved.id == appointment.id


def test_get_appointment_cross_tenant_returns_none(db_session: Session, phase3_test_context: dict):
    """Verify cross-tenant appointment returns None."""
    ctx = phase3_test_context
    starts_at = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)

    appointment = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at,
        timezone_name="Asia/Jakarta",
    )

    # Try to retrieve with wrong salon_id
    wrong_salon_id = uuid.uuid4()
    retrieved = get_appointment(db_session, appointment.id, wrong_salon_id)
    assert retrieved is None


def test_list_appointments_success(db_session: Session, phase3_test_context: dict):
    """Verify appointments can be listed."""
    ctx = phase3_test_context
    starts_at_1 = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
    starts_at_2 = datetime(2026, 10, 15, 14, 0, tzinfo=UTC)

    appointment1 = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at_1,
        timezone_name="Asia/Jakarta",
    )

    appointment2 = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at_2,
        timezone_name="Asia/Jakarta",
    )

    appointments = list_appointments(db_session, ctx["salon"].id)
    assert len(appointments) == 2
    assert appointments[0].id == appointment1.id
    assert appointments[1].id == appointment2.id


def test_list_appointments_filtered_by_status(db_session: Session, phase3_test_context: dict):
    """Verify appointments can be filtered by status."""
    ctx = phase3_test_context
    starts_at_1 = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
    starts_at_2 = datetime(2026, 10, 15, 14, 0, tzinfo=UTC)

    appointment1 = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at_1,
        timezone_name="Asia/Jakarta",
    )

    appointment2 = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at_2,
        timezone_name="Asia/Jakarta",
    )

    change_appointment_status(db_session, appointment2, "confirmed")

    scheduled = list_appointments(db_session, ctx["salon"].id, status="scheduled")
    assert len(scheduled) == 1
    assert scheduled[0].id == appointment1.id

    confirmed = list_appointments(db_session, ctx["salon"].id, status="confirmed")
    assert len(confirmed) == 1
    assert confirmed[0].id == appointment2.id


def test_list_appointments_filtered_by_date_range(db_session: Session, phase3_test_context: dict):
    """Verify appointments can be filtered by date range."""
    ctx = phase3_test_context

    # Create appointments across different dates
    starts_at_1 = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)
    starts_at_2 = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
    starts_at_3 = datetime(2026, 10, 16, 10, 0, tzinfo=UTC)

    appointment1 = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at_1,
        timezone_name="Asia/Jakarta",
    )

    appointment2 = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at_2,
        timezone_name="Asia/Jakarta",
    )

    appointment3 = create_appointment(
        db=db_session,
        salon_id=ctx["salon"].id,
        customer_id=ctx["customer"].id,
        service_id=ctx["service"].id,
        staff_profile_id=ctx["staff_profile"].id,
        starts_at=starts_at_3,
        timezone_name="Asia/Jakarta",
    )

    # Filter: starts_after Oct 15 00:00
    filtered = list_appointments(
        db_session,
        ctx["salon"].id,
        starts_after=datetime(2026, 10, 15, 0, 0, tzinfo=UTC),
    )
    assert len(filtered) == 2
    assert appointment2.id in [a.id for a in filtered]
    assert appointment3.id in [a.id for a in filtered]

    # Filter: starts_before Oct 16 00:00
    filtered = list_appointments(
        db_session,
        ctx["salon"].id,
        starts_before=datetime(2026, 10, 16, 0, 0, tzinfo=UTC),
    )
    assert len(filtered) == 2
    assert appointment1.id in [a.id for a in filtered]
    assert appointment2.id in [a.id for a in filtered]
