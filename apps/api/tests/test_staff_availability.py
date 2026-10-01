"""P2-D Staff Weekly Availability API contract tests."""

import pytest
from app.core.security import hash_password
from app.main import app
from app.models import Salon, SalonMembership, StaffProfile, User
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


def _create_profile(db_session: Session, membership: SalonMembership) -> StaffProfile:
    profile = StaffProfile(membership_id=membership.id)
    db_session.add(profile)
    db_session.commit()
    return profile


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def availability_setup(db_session: Session) -> dict[str, object]:
    owner, owner_token = _create_user(db_session, "avail-owner@example.com")
    manager, manager_token = _create_user(db_session, "avail-manager@example.com")
    staff1, staff1_token = _create_user(db_session, "avail-staff1@example.com")
    staff2, staff2_token = _create_user(db_session, "avail-staff2@example.com")

    salon = _create_salon(db_session, owner, "avail")

    owner_membership = _add_membership(db_session, salon, owner, "owner")
    manager_membership = _add_membership(db_session, salon, manager, "manager")
    staff1_membership = _add_membership(db_session, salon, staff1, "staff")
    staff2_membership = _add_membership(db_session, salon, staff2, "staff")

    owner_profile = _create_profile(db_session, owner_membership)
    manager_profile = _create_profile(db_session, manager_membership)
    staff1_profile = _create_profile(db_session, staff1_membership)
    staff2_profile = _create_profile(db_session, staff2_membership)

    return {
        "salon": salon,
        "owner": owner,
        "owner_token": owner_token,
        "owner_profile": owner_profile,
        "manager": manager,
        "manager_token": manager_token,
        "manager_profile": manager_profile,
        "staff1": staff1,
        "staff1_token": staff1_token,
        "staff1_profile": staff1_profile,
        "staff2": staff2,
        "staff2_token": staff2_token,
        "staff2_profile": staff2_profile,
    }


# ============================================================================
# RBAC: Create Tests
# ============================================================================


def test_owner_create_availability(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["owner_token"])),
        json={
            "day_of_week": 1,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["day_of_week"] == 1
    assert data["start_time"] == "09:00:00"
    assert data["end_time"] == "17:00:00"
    assert data["staff_profile_id"] == str(staff1_profile.id)
    assert data["is_available"] is True


def test_manager_create_availability(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["manager_token"])),
        json={
            "day_of_week": 2,
            "start_time": "10:00:00",
            "end_time": "18:00:00",
        },
    )

    assert response.status_code == 201
    assert response.json()["day_of_week"] == 2


def test_staff_create_own_availability(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["staff1_token"])),
        json={
            "day_of_week": 0,
            "start_time": "08:00:00",
            "end_time": "16:00:00",
        },
    )

    assert response.status_code == 201
    assert response.json()["day_of_week"] == 0


def test_staff_cannot_create_for_another_profile(
    availability_setup: dict[str, object],
) -> None:
    salon = availability_setup["salon"]
    staff2_profile = availability_setup["staff2_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff2_profile, StaffProfile)

    # staff1 attempts to create for staff2
    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff2_profile.id}/availability",
        headers=_auth(str(availability_setup["staff1_token"])),
        json={
            "day_of_week": 0,
            "start_time": "08:00:00",
            "end_time": "16:00:00",
        },
    )

    assert response.status_code == 403


# ============================================================================
# RBAC: Read Tests
# ============================================================================


def test_all_roles_read_availability(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    # Create slot
    client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["owner_token"])),
        json={
            "day_of_week": 1,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
        },
    )

    for role_token_key in ("owner_token", "manager_token", "staff1_token", "staff2_token"):
        token = str(availability_setup[role_token_key])
        response = client.get(
            f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
            headers=_auth(token),
        )
        assert response.status_code == 200
        slots = response.json()
        assert len(slots) == 1
        assert slots[0]["start_time"] == "09:00:00"


# ============================================================================
# RBAC: Update Tests
# ============================================================================


def test_owner_update_availability(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    res = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["owner_token"])),
        json={"day_of_week": 1, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    slot_id = res.json()["id"]

    response = client.patch(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability/{slot_id}",
        headers=_auth(str(availability_setup["owner_token"])),
        json={"start_time": "10:00:00"},
    )
    assert response.status_code == 200
    assert response.json()["start_time"] == "10:00:00"


def test_manager_update_availability(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    res = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["owner_token"])),
        json={"day_of_week": 1, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    slot_id = res.json()["id"]

    response = client.patch(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability/{slot_id}",
        headers=_auth(str(availability_setup["manager_token"])),
        json={"end_time": "13:00:00"},
    )
    assert response.status_code == 200
    assert response.json()["end_time"] == "13:00:00"


def test_staff_update_own_availability(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    res = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["staff1_token"])),
        json={"day_of_week": 1, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    slot_id = res.json()["id"]

    response = client.patch(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability/{slot_id}",
        headers=_auth(str(availability_setup["staff1_token"])),
        json={"start_time": "09:30:00"},
    )
    assert response.status_code == 200
    assert response.json()["start_time"] == "09:30:00"


def test_staff_cannot_update_another_profile(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff2_profile = availability_setup["staff2_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff2_profile, StaffProfile)

    res = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff2_profile.id}/availability",
        headers=_auth(str(availability_setup["owner_token"])),
        json={"day_of_week": 1, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    slot_id = res.json()["id"]

    # staff1 attempts to patch staff2's slot
    response = client.patch(
        f"/salons/{salon.id}/staff-profiles/{staff2_profile.id}/availability/{slot_id}",
        headers=_auth(str(availability_setup["staff1_token"])),
        json={"start_time": "10:00:00"},
    )
    assert response.status_code == 403


# ============================================================================
# RBAC: Delete Tests
# ============================================================================


def test_owner_delete_availability(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    res = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["owner_token"])),
        json={"day_of_week": 1, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    slot_id = res.json()["id"]

    response = client.delete(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability/{slot_id}",
        headers=_auth(str(availability_setup["owner_token"])),
    )
    assert response.status_code == 204


def test_manager_delete_availability(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    res = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["owner_token"])),
        json={"day_of_week": 1, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    slot_id = res.json()["id"]

    response = client.delete(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability/{slot_id}",
        headers=_auth(str(availability_setup["manager_token"])),
    )
    assert response.status_code == 204


def test_staff_delete_own_availability(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    res = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["staff1_token"])),
        json={"day_of_week": 1, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    slot_id = res.json()["id"]

    response = client.delete(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability/{slot_id}",
        headers=_auth(str(availability_setup["staff1_token"])),
    )
    assert response.status_code == 204


def test_staff_cannot_delete_another_profile(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff2_profile = availability_setup["staff2_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff2_profile, StaffProfile)

    res = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff2_profile.id}/availability",
        headers=_auth(str(availability_setup["owner_token"])),
        json={"day_of_week": 1, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    slot_id = res.json()["id"]

    response = client.delete(
        f"/salons/{salon.id}/staff-profiles/{staff2_profile.id}/availability/{slot_id}",
        headers=_auth(str(availability_setup["staff1_token"])),
    )
    assert response.status_code == 403


# ============================================================================
# Cross-Tenant Resource Isolation Tests -> 404
# ============================================================================


def test_cross_tenant_staff_profile_returns_404(
    db_session: Session, availability_setup: dict[str, object]
) -> None:
    salon = availability_setup["salon"]
    assert isinstance(salon, Salon)

    # Create another salon with another owner and profile
    other_owner, other_token = _create_user(db_session, "other-avail-owner@example.com")
    other_salon = _create_salon(db_session, other_owner, "other-avail")
    other_membership = _add_membership(db_session, other_salon, other_owner, "owner")
    other_profile = _create_profile(db_session, other_membership)

    # Try to access other_profile under salon.id
    response = client.get(
        f"/salons/{salon.id}/staff-profiles/{other_profile.id}/availability",
        headers=_auth(str(availability_setup["owner_token"])),
    )
    assert response.status_code == 404


def test_cross_tenant_availability_returns_404(
    db_session: Session, availability_setup: dict[str, object]
) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    # Create slot in salon
    res = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["owner_token"])),
        json={"day_of_week": 1, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    slot_id = res.json()["id"]

    # Create other salon
    other_owner, other_token = _create_user(db_session, "other-avail2-owner@example.com")
    other_salon = _create_salon(db_session, other_owner, "other-avail2")
    _add_membership(db_session, other_salon, other_owner, "owner")

    # Try to access slot_id from other_salon
    response = client.delete(
        f"/salons/{other_salon.id}/staff-profiles/{staff1_profile.id}/availability/{slot_id}",
        headers=_auth(other_token),
    )
    assert response.status_code == 404


# ============================================================================
# Validation: Weekday and Time Order Tests -> 422
# ============================================================================


def test_invalid_weekday_returns_422(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    # day_of_week = 7 is invalid (0..6 valid)
    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["owner_token"])),
        json={"day_of_week": 7, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    assert response.status_code == 422

    # day_of_week = -1 is invalid
    response_neg = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["owner_token"])),
        json={"day_of_week": -1, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    assert response_neg.status_code == 422


def test_start_time_ge_end_time_returns_422(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    # start_time == end_time
    response_eq = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["owner_token"])),
        json={"day_of_week": 1, "start_time": "12:00:00", "end_time": "12:00:00"},
    )
    assert response_eq.status_code == 422

    # start_time > end_time
    response_gt = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(str(availability_setup["owner_token"])),
        json={"day_of_week": 1, "start_time": "14:00:00", "end_time": "12:00:00"},
    )
    assert response_gt.status_code == 422


# ============================================================================
# Overlap Scenarios Tests: Overlap Rule (409) vs Allowed Adjacent
# ============================================================================


def test_overlap_matrix_rejections_and_allowances(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    owner_token = str(availability_setup["owner_token"])
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    # Setup baseline slot: Monday (day 0) 09:00 - 12:00
    base_res = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(owner_token),
        json={"day_of_week": 0, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    assert base_res.status_code == 201

    # WAJIB REJECT 409:
    # 1. exact duplicate: 09:00 - 12:00
    r_exact = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(owner_token),
        json={"day_of_week": 0, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    assert r_exact.status_code == 409

    # 2. partial overlap left: 08:00 - 10:00
    r_left = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(owner_token),
        json={"day_of_week": 0, "start_time": "08:00:00", "end_time": "10:00:00"},
    )
    assert r_left.status_code == 409

    # 3. partial overlap right: 10:00 - 13:00
    r_right = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(owner_token),
        json={"day_of_week": 0, "start_time": "10:00:00", "end_time": "13:00:00"},
    )
    assert r_right.status_code == 409

    # 4. contained interval: 09:30 - 11:00
    r_contained = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(owner_token),
        json={"day_of_week": 0, "start_time": "09:30:00", "end_time": "11:00:00"},
    )
    assert r_contained.status_code == 409

    # 5. containing interval: 08:00 - 13:00
    r_containing = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(owner_token),
        json={"day_of_week": 0, "start_time": "08:00:00", "end_time": "13:00:00"},
    )
    assert r_containing.status_code == 409

    # WAJIB ALLOW:
    # 1. adjacent before: 07:00 - 09:00
    r_adj_before = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(owner_token),
        json={"day_of_week": 0, "start_time": "07:00:00", "end_time": "09:00:00"},
    )
    assert r_adj_before.status_code == 201

    # 2. adjacent after: 12:00 - 14:00
    r_adj_after = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(owner_token),
        json={"day_of_week": 0, "start_time": "12:00:00", "end_time": "14:00:00"},
    )
    assert r_adj_after.status_code == 201

    # Same time on DIFFERENT weekday is allowed
    r_diff_day = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(owner_token),
        json={"day_of_week": 1, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    assert r_diff_day.status_code == 201


def test_patch_excludes_current_slot(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    owner_token = str(availability_setup["owner_token"])
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    # Create slot: 09:00 - 12:00
    base_res = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(owner_token),
        json={"day_of_week": 0, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    slot_id = base_res.json()["id"]

    # PATCH to slightly different time within itself or same time should NOT conflict with itself
    patch_res = client.patch(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability/{slot_id}",
        headers=_auth(owner_token),
        json={"start_time": "09:15:00"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["start_time"] == "09:15:00"


def test_patch_creating_overlap_returns_409(availability_setup: dict[str, object]) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    owner_token = str(availability_setup["owner_token"])
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    # Slot 1: 09:00 - 12:00
    res1 = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(owner_token),
        json={"day_of_week": 0, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    assert res1.status_code == 201

    # Slot 2: 13:00 - 16:00
    res2 = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(owner_token),
        json={"day_of_week": 0, "start_time": "13:00:00", "end_time": "16:00:00"},
    )
    slot2_id = res2.json()["id"]

    # Try to PATCH Slot 2 to 11:00 - 15:00 (overlaps with Slot 1: 09:00 - 12:00)
    response = client.patch(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability/{slot2_id}",
        headers=_auth(owner_token),
        json={"start_time": "11:00:00"},
    )
    assert response.status_code == 409


# ============================================================================
# DB IntegrityError Handling Tests
# ============================================================================


def test_availability_deterministic_db_integrity_error_mapped_to_409(
    monkeypatch: pytest.MonkeyPatch, availability_setup: dict[str, object]
) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    owner_token = str(availability_setup["owner_token"])
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    from app.routers import availability as avail_module

    class DummyDiag:
        constraint_name = "uq_staff_weekly_availability_staff_day_start"

    class DummyOrig(Exception):
        diag = DummyDiag()

    def fake_create(*args, **kwargs):
        raise IntegrityError("duplicate key", None, DummyOrig())

    monkeypatch.setattr(avail_module, "create_availability", fake_create)

    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(owner_token),
        json={"day_of_week": 0, "start_time": "09:00:00", "end_time": "12:00:00"},
    )
    assert response.status_code == 409
    assert "duplicate" in response.json()["detail"].lower()


def test_unrelated_integrity_error_is_not_converted_to_409(
    monkeypatch: pytest.MonkeyPatch, availability_setup: dict[str, object]
) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    owner_token = str(availability_setup["owner_token"])
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    from app.routers import availability as avail_module

    class DummyDiag:
        constraint_name = "some_unrelated_foreign_key_constraint"

    class DummyOrig(Exception):
        diag = DummyDiag()

    def fake_create(*args, **kwargs):
        raise IntegrityError("foreign key violation", None, DummyOrig())

    monkeypatch.setattr(avail_module, "create_availability", fake_create)

    # When unrelated IntegrityError is raised, it must not be caught as 409 (it raises uncaught/500)
    with pytest.raises(IntegrityError):
        client.post(
            f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
            headers=_auth(owner_token),
            json={"day_of_week": 0, "start_time": "09:00:00", "end_time": "12:00:00"},
        )


# ============================================================================
# PATCH Validation: Explicit Null Rejection
# ============================================================================


@pytest.mark.parametrize(
    "payload",
    [
        {"day_of_week": None},
        {"start_time": None},
        {"end_time": None},
        {"day_of_week": None, "start_time": None, "end_time": None},
    ],
)
def test_patch_availability_rejects_explicit_null(
    payload: dict, availability_setup: dict[str, object]
) -> None:
    salon = availability_setup["salon"]
    staff1_profile = availability_setup["staff1_profile"]
    owner_token = str(availability_setup["owner_token"])
    assert isinstance(salon, Salon)
    assert isinstance(staff1_profile, StaffProfile)

    # Create initial slot
    res = client.post(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability",
        headers=_auth(owner_token),
        json={"day_of_week": 0, "start_time": "09:00:00", "end_time": "17:00:00"},
    )
    assert res.status_code == 201
    slot_id = res.json()["id"]

    # PATCH with explicit null must be rejected with 422
    patch_res = client.patch(
        f"/salons/{salon.id}/staff-profiles/{staff1_profile.id}/availability/{slot_id}",
        headers=_auth(owner_token),
        json=payload,
    )
    assert patch_res.status_code == 422
