"""P2-C Audit Remediation Tests: FK conflict, concurrent duplicate, suspended member."""

import pytest
from app.core.security import hash_password
from app.main import app
from app.models import Salon, SalonMembership, SalonService, StaffProfile, User
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

client = TestClient(app)


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


def _add_membership(
    db_session: Session, salon: Salon, user: User, role: str, status: str = "active"
) -> SalonMembership:
    membership = SalonMembership(salon_id=salon.id, user_id=user.id, role=role, status=status)
    db_session.add(membership)
    db_session.commit()
    return membership


def _create_service(db_session: Session, salon: Salon, name: str) -> SalonService:
    service = SalonService(
        salon_id=salon.id,
        name=name,
        duration_minutes=30,
        price_amount=50000,
        currency="IDR",
    )
    db_session.add(service)
    db_session.commit()
    return service


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# Audit Issue 1: Member Removal FK Conflict → 409
# ============================================================================


def test_delete_member_with_staff_profile_returns_409(db_session: Session) -> None:
    """Member with operational StaffProfile cannot be hard-deleted (use suspend)."""
    owner, owner_token = _create_user(db_session, "audit-owner@example.com")
    staff_user, staff_token = _create_user(db_session, "audit-staff@example.com")
    salon = _create_salon(db_session, owner, "audit-delete")

    _add_membership(db_session, salon, owner, "owner")
    staff_membership = _add_membership(db_session, salon, staff_user, "staff")

    # Store IDs before API calls
    salon_id = salon.id
    staff_membership_id = staff_membership.id

    # Create StaffProfile for staff member
    response_profile = client.post(
        f"/salons/{salon_id}/staff-profiles",
        headers=_auth(owner_token),
        json={"membership_id": str(staff_membership_id)},
    )
    assert response_profile.status_code == 201
    profile_id = response_profile.json()["id"]

    # Try to DELETE member (should fail with 409, not 500)
    response = client.delete(
        f"/salons/{salon_id}/members/{staff_membership_id}",
        headers=_auth(owner_token),
    )

    assert response.status_code == 409
    assert "operational staff profile" in response.json()["detail"].lower()

    verify_membership = db_session.get(SalonMembership, staff_membership_id)
    assert verify_membership is not None
    assert db_session.get(StaffProfile, profile_id) is not None


def test_delete_member_with_staff_profile_and_assignment_returns_409(
    db_session: Session,
) -> None:
    """Member with StaffProfile + assignment cannot be hard-deleted."""
    owner, owner_token = _create_user(db_session, "audit-owner2@example.com")
    staff_user, staff_token = _create_user(db_session, "audit-staff2@example.com")
    salon = _create_salon(db_session, owner, "audit-delete2")

    _add_membership(db_session, salon, owner, "owner")
    staff_membership = _add_membership(db_session, salon, staff_user, "staff")
    service = _create_service(db_session, salon, "Haircut")

    # Store IDs before API calls
    salon_id = salon.id
    staff_membership_id = staff_membership.id
    service_id = service.id

    # Create StaffProfile
    response_profile = client.post(
        f"/salons/{salon_id}/staff-profiles",
        headers=_auth(owner_token),
        json={"membership_id": str(staff_membership_id)},
    )
    profile_id = response_profile.json()["id"]

    # Create assignment
    response_assign = client.post(
        f"/salons/{salon_id}/staff-profiles/{profile_id}/services/{service_id}",
        headers=_auth(owner_token),
    )
    assert response_assign.status_code == 201

    # Try to DELETE member (should fail with 409)
    response = client.delete(
        f"/salons/{salon_id}/members/{staff_membership_id}",
        headers=_auth(owner_token),
    )

    assert response.status_code == 409


def test_delete_member_without_profile_succeeds(db_session: Session) -> None:
    """Member without StaffProfile can still be hard-deleted (Phase 1 behavior)."""
    owner, owner_token = _create_user(db_session, "audit-owner3@example.com")
    staff_user, staff_token = _create_user(db_session, "audit-staff3@example.com")
    salon = _create_salon(db_session, owner, "audit-delete3")

    _add_membership(db_session, salon, owner, "owner")
    staff_membership = _add_membership(db_session, salon, staff_user, "staff")

    # DELETE member without StaffProfile (should succeed)
    response = client.delete(
        f"/salons/{salon.id}/members/{staff_membership.id}",
        headers=_auth(owner_token),
    )

    assert response.status_code == 200
    assert "removed successfully" in response.json()["message"].lower()

    # Verify membership deleted
    verify_membership = db_session.get(SalonMembership, staff_membership.id)
    assert verify_membership is None


def test_suspend_member_with_profile_succeeds(db_session: Session) -> None:
    """Member with StaffProfile can be suspended (correct lifecycle management)."""
    owner, owner_token = _create_user(db_session, "audit-owner4@example.com")
    staff_user, staff_token = _create_user(db_session, "audit-staff4@example.com")
    salon = _create_salon(db_session, owner, "audit-suspend")

    _add_membership(db_session, salon, owner, "owner")
    staff_membership = _add_membership(db_session, salon, staff_user, "staff")

    # Create StaffProfile
    response_profile = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(owner_token),
        json={"membership_id": str(staff_membership.id)},
    )
    assert response_profile.status_code == 201

    # PATCH status to suspended (should succeed)
    response = client.patch(
        f"/salons/{salon.id}/members/{staff_membership.id}",
        headers=_auth(owner_token),
        json={"status": "suspended"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "suspended"

    # Verify membership and profile still exist
    verify_membership = db_session.get(SalonMembership, staff_membership.id)
    assert verify_membership is not None
    assert verify_membership.status == "suspended"


# ============================================================================
# Audit Issue 2: Concurrent Duplicate IntegrityError → 409
# ============================================================================


def test_concurrent_duplicate_staff_profile_integrity_error_409(db_session: Session) -> None:
    """DB UNIQUE constraint on membership_id maps to 409, not 500."""
    owner, owner_token = _create_user(db_session, "audit-concurrent@example.com")
    staff_user, _ = _create_user(db_session, "audit-concurrent-staff@example.com")
    salon = _create_salon(db_session, owner, "audit-concurrent")

    _add_membership(db_session, salon, owner, "owner")
    staff_membership = _add_membership(db_session, salon, staff_user, "staff")

    # Store IDs before any operations
    salon_id = salon.id
    staff_membership_id = staff_membership.id

    # Create first profile
    response1 = client.post(
        f"/salons/{salon_id}/staff-profiles",
        headers=_auth(owner_token),
        json={"membership_id": str(staff_membership_id)},
    )
    assert response1.status_code == 201

    # Duplicate via API should catch pre-check
    response2 = client.post(
        f"/salons/{salon_id}/staff-profiles",
        headers=_auth(owner_token),
        json={"membership_id": str(staff_membership_id)},
    )

    assert response2.status_code == 409
    assert "already has" in response2.json()["detail"].lower()


def test_concurrent_duplicate_assignment_integrity_error_409(db_session: Session) -> None:
    """DB UNIQUE constraint on (staff_profile_id, salon_service_id) maps to 409."""
    owner, owner_token = _create_user(db_session, "audit-assign@example.com")
    staff_user, _ = _create_user(db_session, "audit-assign-staff@example.com")
    salon = _create_salon(db_session, owner, "audit-assign")

    _add_membership(db_session, salon, owner, "owner")
    staff_membership = _add_membership(db_session, salon, staff_user, "staff")
    service = _create_service(db_session, salon, "Service")

    # Create profile
    response_profile = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(owner_token),
        json={"membership_id": str(staff_membership.id)},
    )
    profile_id = response_profile.json()["id"]

    # Create first assignment
    response1 = client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service.id}",
        headers=_auth(owner_token),
    )
    assert response1.status_code == 201

    # Duplicate assignment should return 409
    response2 = client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service.id}",
        headers=_auth(owner_token),
    )

    assert response2.status_code == 409
    assert "already exists" in response2.json()["detail"].lower()


def test_staff_profile_integrity_error_mapped_to_409(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    """Simulated DB unique constraint IntegrityError in staff_profile router maps to 409."""
    owner, owner_token = _create_user(db_session, "audit-ie-owner@example.com")
    staff_user, _ = _create_user(db_session, "audit-ie-staff@example.com")
    salon = _create_salon(db_session, owner, "audit-ie")

    _add_membership(db_session, salon, owner, "owner")
    staff_membership = _add_membership(db_session, salon, staff_user, "staff")

    from app.routers import staff_profile as sp_module

    class DummyDiag:
        constraint_name = "staff_profiles_membership_id_key"

    class DummyOrig(Exception):
        diag = DummyDiag()

    def fake_create(*args, **kwargs):
        raise IntegrityError("duplicate key", None, DummyOrig())

    monkeypatch.setattr(sp_module, "create_staff_profile", fake_create)

    response = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(owner_token),
        json={"membership_id": str(staff_membership.id)},
    )
    assert response.status_code == 409
    assert "already has a staff profile" in response.json()["detail"].lower()


def test_staff_service_assignment_integrity_error_mapped_to_409(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    """Simulated DB unique constraint IntegrityError in assignment router maps to 409."""
    owner, owner_token = _create_user(db_session, "audit-ie2-owner@example.com")
    staff_user, _ = _create_user(db_session, "audit-ie2-staff@example.com")
    salon = _create_salon(db_session, owner, "audit-ie2")

    _add_membership(db_session, salon, owner, "owner")
    staff_membership = _add_membership(db_session, salon, staff_user, "staff")
    service = _create_service(db_session, salon, "Service")

    # Create profile
    response_profile = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(owner_token),
        json={"membership_id": str(staff_membership.id)},
    )
    profile_id = response_profile.json()["id"]

    from app.routers import staff_profile as sp_module

    class DummyDiag:
        constraint_name = "uq_staff_service_assignments_staff_service"

    class DummyOrig(Exception):
        diag = DummyDiag()

    def fake_create_assignment(*args, **kwargs):
        raise IntegrityError("duplicate key", None, DummyOrig())

    monkeypatch.setattr(sp_module, "create_staff_service_assignment", fake_create_assignment)

    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service.id}",
        headers=_auth(owner_token),
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()
