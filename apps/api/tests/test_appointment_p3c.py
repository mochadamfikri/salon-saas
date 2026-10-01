"""P3-C Appointment API endpoint tests."""

import uuid
from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from app.core.security import hash_password
from app.main import app
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
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

client = TestClient(app)


# ============================================================================
# Fixtures
# ============================================================================


def _create_user(db_session: Session, email: str) -> tuple[User, str]:
    user = User(email=email, password_hash=hash_password("SecurePass123"), is_active=True)
    db_session.add(user)
    db_session.commit()
    response = client.post("/auth/login", json={"email": email, "password": "SecurePass123"})
    return user, response.json()["access_token"]


def _create_salon(db_session: Session, user: User, suffix: str) -> Salon:
    salon = Salon(
        name=f"Salon {suffix}",
        slug=f"salon-{suffix}",
        created_by_user_id=user.id,
    )
    db_session.add(salon)
    db_session.commit()
    return salon


def _add_membership(db_session: Session, salon: Salon, user: User, role: str) -> SalonMembership:
    membership = SalonMembership(salon_id=salon.id, user_id=user.id, role=role, status="active")
    db_session.add(membership)
    db_session.commit()
    return membership


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def p3c_context(db_session: Session) -> dict:
    """Create full Phase 1+2+3 fixture for appointment API tests."""
    unique_suffix = uuid.uuid4().hex[:8]

    owner, owner_token = _create_user(db_session, f"appointment-owner-{unique_suffix}@example.com")
    manager, manager_token = _create_user(
        db_session, f"appointment-manager-{unique_suffix}@example.com"
    )
    staff_user, staff_token = _create_user(
        db_session, f"appointment-staff-{unique_suffix}@example.com"
    )

    salon = _create_salon(db_session, owner, f"appointment-{unique_suffix}")
    _add_membership(db_session, salon, owner, "owner")
    _add_membership(db_session, salon, manager, "manager")
    staff_membership = _add_membership(db_session, salon, staff_user, "staff")

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
        email=f"customer-{unique_suffix}@example.com",
        phone="08123456789",
    )
    db_session.add(customer)
    db_session.commit()

    return {
        "salon": salon,
        "owner_token": owner_token,
        "manager_token": manager_token,
        "staff_token": staff_token,
        "service": service,
        "staff_profile": staff_profile,
        "customer": customer,
    }


# ============================================================================
# Appointment Creation Tests
# ============================================================================


@pytest.mark.parametrize("token_key", ["owner_token", "manager_token", "staff_token"])
def test_all_roles_can_create_appointment(p3c_context: dict, token_key: str) -> None:
    """Verify Owner, Manager, and Staff can create appointments."""
    ctx = p3c_context
    token = str(ctx[token_key])

    # Monday 2026-10-05 10:00 Asia/Jakarta (within availability 09:00-17:00)
    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))

    response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(token),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
            "notes": "Walk-in",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "scheduled"
    assert data["service_name_snapshot"] == "Haircut"
    assert data["duration_minutes_snapshot"] == 30
    assert data["notes"] == "Walk-in"


def test_create_appointment_returns_404_for_cross_tenant_customer(p3c_context: dict) -> None:
    """Verify cross-tenant customer returns 404."""
    ctx = p3c_context
    fake_customer_id = uuid.uuid4()

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(fake_customer_id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_appointment_returns_422_for_inactive_service(p3c_context: dict) -> None:
    """Verify inactive service returns 422."""
    ctx = p3c_context
    ctx["service"].is_active = False

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    assert response.status_code == 422
    assert "not active" in response.json()["detail"].lower()


def test_create_appointment_returns_422_for_unavailable_slot(p3c_context: dict) -> None:
    """Verify booking outside availability returns 422."""
    ctx = p3c_context

    # Monday 2026-10-05 20:00 Asia/Jakarta (outside 09:00-17:00)
    starts_at = datetime(2026, 10, 5, 20, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    assert response.status_code == 422
    assert "not available" in response.json()["detail"].lower()


def test_create_appointment_returns_409_for_overlap(p3c_context: dict) -> None:
    """Verify overlapping appointments return 409."""
    ctx = p3c_context

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    payload = {
        "customer_id": str(ctx["customer"].id),
        "service_id": str(ctx["service"].id),
        "staff_profile_id": str(ctx["staff_profile"].id),
        "starts_at": starts_at.isoformat(),
        "timezone": "Asia/Jakarta",
    }

    # First booking succeeds
    response1 = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json=payload,
    )
    assert response1.status_code == 201

    # Overlapping booking fails
    response2 = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json=payload,
    )
    assert response2.status_code == 409
    assert "overlap" in response2.json()["detail"].lower()


def test_create_appointment_allows_adjacent_bookings(p3c_context: dict) -> None:
    """Verify adjacent appointments do not conflict."""
    ctx = p3c_context

    # First appointment 10:00-10:30
    starts_at_1 = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    response1 = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at_1.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    assert response1.status_code == 201

    # Adjacent appointment 10:30-11:00
    starts_at_2 = datetime(2026, 10, 5, 10, 30, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    response2 = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at_2.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    assert response2.status_code == 201


# ============================================================================
# Appointment List & Filter Tests
# ============================================================================


def test_list_appointments_with_filters(p3c_context: dict) -> None:
    """Verify appointment listing with filters and pagination."""
    ctx = p3c_context

    # Create 3 appointments
    for hour in [10, 11, 12]:
        starts_at = datetime(2026, 10, 5, hour, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
        client.post(
            f"/salons/{ctx['salon'].id}/appointments",
            headers=_auth(str(ctx["owner_token"])),
            json={
                "customer_id": str(ctx["customer"].id),
                "service_id": str(ctx["service"].id),
                "staff_profile_id": str(ctx["staff_profile"].id),
                "starts_at": starts_at.isoformat(),
                "timezone": "Asia/Jakarta",
            },
        )

    # List all
    response = client.get(
        f"/salons/{ctx['salon'].id}/appointments", headers=_auth(str(ctx["owner_token"]))
    )
    assert response.status_code == 200
    assert len(response.json()) == 3

    # Filter by staff
    response = client.get(
        f"/salons/{ctx['salon'].id}/appointments?staff_profile_id={ctx['staff_profile'].id}",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response.status_code == 200
    assert len(response.json()) == 3

    # Filter by customer
    response = client.get(
        f"/salons/{ctx['salon'].id}/appointments?customer_id={ctx['customer'].id}",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response.status_code == 200
    assert len(response.json()) == 3

    # Pagination
    response = client.get(
        f"/salons/{ctx['salon'].id}/appointments?limit=2",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_appointments_by_status(p3c_context: dict) -> None:
    """Verify appointment filtering by status."""
    ctx = p3c_context

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    create_response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    appointment_id = create_response.json()["id"]

    # List scheduled
    response = client.get(
        f"/salons/{ctx['salon'].id}/appointments?status=scheduled",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Confirm appointment
    client.post(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}/confirm",
        headers=_auth(str(ctx["owner_token"])),
    )

    # List confirmed
    response = client.get(
        f"/salons/{ctx['salon'].id}/appointments?status=confirmed",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response.status_code == 200
    assert len(response.json()) == 1

    # List scheduled returns empty
    response = client.get(
        f"/salons/{ctx['salon'].id}/appointments?status=scheduled",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response.status_code == 200
    assert len(response.json()) == 0


# ============================================================================
# Appointment Reschedule Tests
# ============================================================================


def test_reschedule_appointment(p3c_context: dict) -> None:
    """Verify appointment rescheduling with validation."""
    ctx = p3c_context

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    create_response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
            "notes": "Original",
        },
    )
    appointment_id = create_response.json()["id"]

    # Reschedule to 11:00
    new_starts_at = datetime(2026, 10, 5, 11, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    response = client.patch(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "starts_at": new_starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
            "notes": "Rescheduled",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["notes"] == "Rescheduled"
    assert datetime.fromisoformat(data["starts_at"]).astimezone(ZoneInfo("Asia/Jakarta")).hour == 11


def test_reschedule_terminal_appointment_fails(p3c_context: dict) -> None:
    """Verify terminal appointments cannot be rescheduled."""
    ctx = p3c_context

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    create_response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    appointment_id = create_response.json()["id"]

    # Complete appointment
    client.post(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}/complete",
        headers=_auth(str(ctx["owner_token"])),
    )

    # Attempt reschedule
    new_starts_at = datetime(2026, 10, 5, 11, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    response = client.patch(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "starts_at": new_starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    assert response.status_code == 422
    assert "terminal" in response.json()["detail"].lower()


def test_reschedule_with_conflict_fails(p3c_context: dict) -> None:
    """Verify rescheduling to overlapping time fails."""
    ctx = p3c_context

    # Create two appointments
    starts_at_1 = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    response1 = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at_1.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    appointment_id_1 = response1.json()["id"]

    starts_at_2 = datetime(2026, 10, 5, 11, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at_2.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )

    # Attempt to reschedule first to overlap second
    response = client.patch(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id_1}",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "starts_at": starts_at_2.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    assert response.status_code == 409
    assert "overlap" in response.json()["detail"].lower()


# ============================================================================
# Status Transition Tests
# ============================================================================


def test_confirm_appointment(p3c_context: dict) -> None:
    """Verify appointment confirmation."""
    ctx = p3c_context

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    create_response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    appointment_id = create_response.json()["id"]

    response = client.post(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}/confirm",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


def test_complete_appointment(p3c_context: dict) -> None:
    """Verify appointment completion."""
    ctx = p3c_context

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    create_response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    appointment_id = create_response.json()["id"]

    response = client.post(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}/complete",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_cancel_appointment(p3c_context: dict) -> None:
    """Verify appointment cancellation."""
    ctx = p3c_context

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    create_response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    appointment_id = create_response.json()["id"]

    response = client.post(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}/cancel",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_no_show_appointment(p3c_context: dict) -> None:
    """Verify appointment no-show marking."""
    ctx = p3c_context

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    create_response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    appointment_id = create_response.json()["id"]

    response = client.post(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}/no-show",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "no_show"


def test_status_transition_idempotent(p3c_context: dict) -> None:
    """Verify status transitions are idempotent."""
    ctx = p3c_context

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    create_response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    appointment_id = create_response.json()["id"]

    # Confirm twice
    response1 = client.post(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}/confirm",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response1.status_code == 200

    response2 = client.post(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}/confirm",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response2.status_code == 200


def test_invalid_terminal_transition_fails(p3c_context: dict) -> None:
    """Verify invalid transitions from terminal states fail."""
    ctx = p3c_context

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    create_response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    appointment_id = create_response.json()["id"]

    # Complete appointment
    client.post(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}/complete",
        headers=_auth(str(ctx["owner_token"])),
    )

    # Attempt to confirm completed appointment
    response = client.post(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}/confirm",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response.status_code == 422
    assert "terminal" in response.json()["detail"].lower()


# ============================================================================
# Cross-Tenant Isolation Tests
# ============================================================================


def test_appointment_cross_tenant_isolation(db_session: Session) -> None:
    """Verify appointments are isolated across tenants."""
    unique_suffix = uuid.uuid4().hex[:8]

    # Salon A
    owner_a, token_a = _create_user(db_session, f"owner-a-{unique_suffix}@example.com")
    salon_a = _create_salon(db_session, owner_a, f"a-{unique_suffix}")
    _add_membership(db_session, salon_a, owner_a, "owner")

    # Salon B
    owner_b, token_b = _create_user(db_session, f"owner-b-{unique_suffix}@example.com")
    salon_b = _create_salon(db_session, owner_b, f"b-{unique_suffix}")
    _add_membership(db_session, salon_b, owner_b, "owner")

    # Create appointment in salon A
    service_a = SalonService(
        salon_id=salon_a.id,
        name="Service A",
        duration_minutes=30,
        price_amount=Decimal("100000"),
        currency="IDR",
        is_active=True,
    )
    db_session.add(service_a)
    membership_a = (
        db_session.query(SalonMembership).filter_by(salon_id=salon_a.id, user_id=owner_a.id).first()
    )
    assert membership_a is not None
    staff_a = StaffProfile(membership_id=membership_a.id, display_name="Staff A", is_bookable=True)
    db_session.add(staff_a)
    db_session.flush()

    assignment_a = StaffServiceAssignment(
        staff_profile_id=staff_a.id, salon_service_id=service_a.id
    )
    db_session.add(assignment_a)
    availability_a = StaffWeeklyAvailability(
        staff_profile_id=staff_a.id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(17, 0),
        is_available=True,
    )
    db_session.add(availability_a)
    customer_a = SalonCustomer(salon_id=salon_a.id, full_name="Customer A")
    db_session.add(customer_a)
    db_session.commit()

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    create_response = client.post(
        f"/salons/{salon_a.id}/appointments",
        headers=_auth(token_a),
        json={
            "customer_id": str(customer_a.id),
            "service_id": str(service_a.id),
            "staff_profile_id": str(staff_a.id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    assert create_response.status_code == 201
    appointment_id = create_response.json()["id"]

    # Owner B cannot see appointment from salon A
    response = client.get(
        f"/salons/{salon_b.id}/appointments/{appointment_id}", headers=_auth(token_b)
    )
    assert response.status_code == 404

    # Owner B cannot list appointments from salon A
    response = client.get(f"/salons/{salon_b.id}/appointments", headers=_auth(token_b))
    assert response.status_code == 200
    assert len(response.json()) == 0


# ============================================================================
# Additional Contract, Filter & Edge-Case Tests
# ============================================================================


def test_hard_delete_not_allowed(p3c_context: dict) -> None:
    """Verify DELETE is not implemented (405 Method Not Allowed)."""
    ctx = p3c_context
    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    create_response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    appointment_id = create_response.json()["id"]

    response = client.delete(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response.status_code == 405


def test_patch_updates_notes_only(p3c_context: dict) -> None:
    """Verify PATCH can update notes without modifying booking time."""
    ctx = p3c_context
    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    create_response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
            "notes": "Initial note",
        },
    )
    appointment_id = create_response.json()["id"]

    response = client.patch(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}",
        headers=_auth(str(ctx["owner_token"])),
        json={"notes": "Updated note only"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["notes"] == "Updated note only"
    assert data["starts_at"] == create_response.json()["starts_at"]
    assert data["ends_at"] == create_response.json()["ends_at"]


def test_patch_requires_starts_at_and_timezone_together(p3c_context: dict) -> None:
    """Verify providing starts_at without timezone (or vice versa) returns 422."""
    ctx = p3c_context
    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    create_response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    appointment_id = create_response.json()["id"]

    # starts_at without timezone
    new_starts_at = datetime(2026, 10, 5, 11, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    response1 = client.patch(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}",
        headers=_auth(str(ctx["owner_token"])),
        json={"starts_at": new_starts_at.isoformat()},
    )
    assert response1.status_code == 422

    # timezone without starts_at
    response2 = client.patch(
        f"/salons/{ctx['salon'].id}/appointments/{appointment_id}",
        headers=_auth(str(ctx["owner_token"])),
        json={"timezone": "Asia/Jakarta"},
    )
    assert response2.status_code == 422


def test_list_appointments_date_range_filter(p3c_context: dict) -> None:
    """Verify list appointments filters accurately by starts_at_gte and starts_at_lte."""
    ctx = p3c_context
    # Create appointments at 10:00, 12:00, 14:00
    for hour in [10, 12, 14]:
        starts_at = datetime(2026, 10, 5, hour, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
        client.post(
            f"/salons/{ctx['salon'].id}/appointments",
            headers=_auth(str(ctx["owner_token"])),
            json={
                "customer_id": str(ctx["customer"].id),
                "service_id": str(ctx["service"].id),
                "staff_profile_id": str(ctx["staff_profile"].id),
                "starts_at": starts_at.isoformat(),
                "timezone": "Asia/Jakarta",
            },
        )

    # Filter gte 11:00 (should return 12:00 and 14:00)
    gte_time = datetime(2026, 10, 5, 11, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    resp_gte = client.get(
        f"/salons/{ctx['salon'].id}/appointments",
        params={"starts_at_gte": gte_time.isoformat()},
        headers=_auth(str(ctx["owner_token"])),
    )
    assert resp_gte.status_code == 200
    assert len(resp_gte.json()) == 2

    # Filter lte 13:00 (should return 10:00 and 12:00)
    lte_time = datetime(2026, 10, 5, 13, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    resp_lte = client.get(
        f"/salons/{ctx['salon'].id}/appointments",
        params={"starts_at_lte": lte_time.isoformat()},
        headers=_auth(str(ctx["owner_token"])),
    )
    assert resp_lte.status_code == 200
    assert len(resp_lte.json()) == 2

    # Filter between 11:00 and 13:00 (should return only 12:00)
    resp_window = client.get(
        f"/salons/{ctx['salon'].id}/appointments",
        params={"starts_at_gte": gte_time.isoformat(), "starts_at_lte": lte_time.isoformat()},
        headers=_auth(str(ctx["owner_token"])),
    )
    assert resp_window.status_code == 200
    assert len(resp_window.json()) == 1


def test_list_appointments_invalid_status_filter_fails(p3c_context: dict) -> None:
    """Verify invalid status query param is rejected with 422."""
    ctx = p3c_context
    response = client.get(
        f"/salons/{ctx['salon'].id}/appointments?status=nonexistent",
        headers=_auth(str(ctx["owner_token"])),
    )
    assert response.status_code == 422


def test_unauthenticated_request_returns_401(p3c_context: dict) -> None:
    """Verify request without auth header returns 401."""
    ctx = p3c_context
    response = client.get(f"/salons/{ctx['salon'].id}/appointments")
    assert response.status_code == 401


def test_non_member_request_returns_404(p3c_context: dict, db_session: Session) -> None:
    """Verify non-member cannot probe salon appointments (returns 404)."""
    ctx = p3c_context
    other_user, other_token = _create_user(db_session, "outsider@example.com")
    response = client.get(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(other_token),
    )
    assert response.status_code == 404


def test_create_appointment_missing_staff_assignment_fails(
    p3c_context: dict, db_session: Session
) -> None:
    """Verify booking fails with 422 when staff is not assigned to service."""
    ctx = p3c_context
    # Delete assignment
    db_session.query(StaffServiceAssignment).filter_by(
        staff_profile_id=ctx["staff_profile"].id, salon_service_id=ctx["service"].id
    ).delete()
    db_session.commit()

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    assert response.status_code == 422
    assert "not assigned" in response.json()["detail"].lower()


def test_create_appointment_non_bookable_staff_fails(
    p3c_context: dict, db_session: Session
) -> None:
    """Verify booking fails with 422 when staff is not bookable."""
    ctx = p3c_context
    ctx["staff_profile"].is_bookable = False
    db_session.commit()

    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    response = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    assert response.status_code == 422
    assert "not bookable" in response.json()["detail"].lower()


def test_reschedule_to_slot_occupied_by_cancelled_appointment_succeeds(p3c_context: dict) -> None:
    """Verify cancelled appointment does not block rescheduling into that slot."""
    ctx = p3c_context

    # Create appointment 1 at 10:00 and cancel it
    starts_at_1 = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    resp1 = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at_1.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    appt1_id = resp1.json()["id"]
    client.post(
        f"/salons/{ctx['salon'].id}/appointments/{appt1_id}/cancel",
        headers=_auth(str(ctx["owner_token"])),
    )

    # Create appointment 2 at 11:00
    starts_at_2 = datetime(2026, 10, 5, 11, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    resp2 = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at_2.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    appt2_id = resp2.json()["id"]

    # Reschedule appointment 2 into appointment 1's cancelled slot (10:00)
    resched_resp = client.patch(
        f"/salons/{ctx['salon'].id}/appointments/{appt2_id}",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "starts_at": starts_at_1.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    assert resched_resp.status_code == 200
    assert (
        datetime.fromisoformat(resched_resp.json()["starts_at"])
        .astimezone(ZoneInfo("Asia/Jakarta"))
        .hour
        == 10
    )


def test_reschedule_same_appointment_same_time_succeeds(p3c_context: dict) -> None:
    """Verify an appointment can be rescheduled to its own current time (self-exclusion)."""
    ctx = p3c_context
    starts_at = datetime(2026, 10, 5, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
    resp = client.post(
        f"/salons/{ctx['salon'].id}/appointments",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "customer_id": str(ctx["customer"].id),
            "service_id": str(ctx["service"].id),
            "staff_profile_id": str(ctx["staff_profile"].id),
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    appt_id = resp.json()["id"]

    resched_resp = client.patch(
        f"/salons/{ctx['salon'].id}/appointments/{appt_id}",
        headers=_auth(str(ctx["owner_token"])),
        json={
            "starts_at": starts_at.isoformat(),
            "timezone": "Asia/Jakarta",
            "notes": "Updated note during self-reschedule",
        },
    )
    assert resched_resp.status_code == 200
    assert resched_resp.json()["notes"] == "Updated note during self-reschedule"
