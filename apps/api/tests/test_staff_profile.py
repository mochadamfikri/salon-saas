"""P2-C Staff Profile and Staff-Service Assignment API contract tests."""

import pytest
from app.core.security import hash_password
from app.main import app
from app.models import Salon, SalonMembership, SalonService, StaffProfile, User
from fastapi.testclient import TestClient
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


@pytest.fixture
def staff_profile_users(db_session: Session) -> dict[str, object]:
    owner, owner_token = _create_user(db_session, "profile-owner@example.com")
    manager, manager_token = _create_user(db_session, "profile-manager@example.com")
    staff1, staff1_token = _create_user(db_session, "profile-staff1@example.com")
    staff2, staff2_token = _create_user(db_session, "profile-staff2@example.com")
    suspended, suspended_token = _create_user(db_session, "profile-suspended@example.com")

    salon = _create_salon(db_session, owner, "profiles")

    owner_membership = _add_membership(db_session, salon, owner, "owner")
    manager_membership = _add_membership(db_session, salon, manager, "manager")
    staff1_membership = _add_membership(db_session, salon, staff1, "staff")
    staff2_membership = _add_membership(db_session, salon, staff2, "staff")
    suspended_membership = _add_membership(db_session, salon, suspended, "staff", "suspended")

    service1 = _create_service(db_session, salon, "Haircut")
    service2 = _create_service(db_session, salon, "Coloring")

    return {
        "salon": salon,
        "owner": owner,
        "owner_token": owner_token,
        "owner_membership": owner_membership,
        "manager": manager,
        "manager_token": manager_token,
        "manager_membership": manager_membership,
        "staff1": staff1,
        "staff1_token": staff1_token,
        "staff1_membership": staff1_membership,
        "staff2": staff2,
        "staff2_token": staff2_token,
        "staff2_membership": staff2_membership,
        "suspended_membership": suspended_membership,
        "suspended_token": suspended_token,
        "service1": service1,
        "service2": service2,
    }


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# Staff Profile Creation Tests
# ============================================================================


def test_owner_creates_profile_for_staff(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)

    response = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["membership_id"] == str(staff1_membership.id)
    assert payload["display_name"] is None
    assert payload["phone"] is None
    assert payload["bio"] is None
    assert payload["photo_url"] is None
    assert payload["is_bookable"] is True
    assert payload["created_at"]
    assert payload["updated_at"]

    saved = db_session.get(StaffProfile, payload["id"])
    assert saved is not None
    assert saved.membership_id == staff1_membership.id


def test_manager_creates_profile(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff2_membership = staff_profile_users["staff2_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff2_membership, SalonMembership)

    response = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["manager_token"])),
        json={"membership_id": str(staff2_membership.id)},
    )

    assert response.status_code == 201
    assert response.json()["membership_id"] == str(staff2_membership.id)


def test_owner_membership_can_have_profile(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    """Owner membership can also have a staff profile (owner can be service provider)."""
    salon = staff_profile_users["salon"]
    owner_membership = staff_profile_users["owner_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(owner_membership, SalonMembership)

    response = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(owner_membership.id)},
    )

    assert response.status_code == 201
    assert response.json()["membership_id"] == str(owner_membership.id)


def test_manager_membership_can_have_profile(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    """Manager membership can also have a staff profile (manager can be service provider)."""
    salon = staff_profile_users["salon"]
    manager_membership = staff_profile_users["manager_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(manager_membership, SalonMembership)

    response = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(manager_membership.id)},
    )

    assert response.status_code == 201
    assert response.json()["membership_id"] == str(manager_membership.id)


def test_staff_cannot_create_own_profile(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)

    response = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["staff1_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )

    assert response.status_code == 403


def test_duplicate_membership_profile_returns_409(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)

    # Create first profile
    response1 = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    assert response1.status_code == 201

    # Try to create duplicate
    response2 = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    assert response2.status_code == 409


def test_cross_salon_membership_returns_404(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    """Cannot create profile for membership from another salon."""
    salon = staff_profile_users["salon"]
    owner = staff_profile_users["owner"]
    assert isinstance(salon, Salon)
    assert isinstance(owner, User)

    # Create another salon and membership
    other_owner, other_token = _create_user(db_session, "other-owner@example.com")
    other_salon = _create_salon(db_session, other_owner, "other")
    other_membership = _add_membership(db_session, other_salon, other_owner, "owner")

    # Try to create profile in first salon for membership from other salon
    response = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(other_membership.id)},
    )

    assert response.status_code == 404


def test_suspended_target_membership_rejected(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    """Cannot create profile for suspended membership."""
    salon = staff_profile_users["salon"]
    suspended_membership = staff_profile_users["suspended_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(suspended_membership, SalonMembership)

    response = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(suspended_membership.id)},
    )

    assert response.status_code == 422


# ============================================================================
# Staff Profile Read Tests
# ============================================================================


def test_owner_can_list_all_profiles(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    staff2_membership = staff_profile_users["staff2_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)
    assert isinstance(staff2_membership, SalonMembership)

    # Create two profiles
    client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff2_membership.id)},
    )

    # Owner lists all
    response = client.get(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
    )

    assert response.status_code == 200
    profiles = response.json()
    assert len(profiles) == 2


def test_manager_can_read_all_profiles(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)

    # Create profile
    response_create = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_create.json()["id"]

    # Manager reads it
    response = client.get(
        f"/salons/{salon.id}/staff-profiles/{profile_id}",
        headers=_auth(str(staff_profile_users["manager_token"])),
    )

    assert response.status_code == 200


def test_staff_can_list_same_tenant_profiles(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    staff2_membership = staff_profile_users["staff2_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)
    assert isinstance(staff2_membership, SalonMembership)

    # Create two profiles
    client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff2_membership.id)},
    )

    # Staff1 lists all profiles
    response = client.get(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["staff1_token"])),
    )

    assert response.status_code == 200
    profiles = response.json()
    assert len(profiles) == 2


# ============================================================================
# Staff Profile Update Tests
# ============================================================================


def test_staff_can_update_own_personal_fields(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)

    # Create profile for staff1
    response_create = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_create.json()["id"]

    # Staff1 updates own profile
    response = client.patch(
        f"/salons/{salon.id}/staff-profiles/{profile_id}",
        headers=_auth(str(staff_profile_users["staff1_token"])),
        json={
            "display_name": "John Stylist",
            "phone": "+6281234567890",
            "bio": "Expert stylist",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["display_name"] == "John Stylist"
    assert payload["phone"] == "+6281234567890"
    assert payload["bio"] == "Expert stylist"


def test_staff_cannot_update_another_profile(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff2_membership = staff_profile_users["staff2_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff2_membership, SalonMembership)

    # Create profile for staff2
    response_create = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff2_membership.id)},
    )
    profile_id = response_create.json()["id"]

    # Staff1 tries to update staff2's profile
    response = client.patch(
        f"/salons/{salon.id}/staff-profiles/{profile_id}",
        headers=_auth(str(staff_profile_users["staff1_token"])),
        json={"display_name": "Hacked"},
    )

    assert response.status_code == 403


def test_staff_cannot_toggle_is_bookable(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)

    # Create profile for staff1
    response_create = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_create.json()["id"]

    # Staff1 tries to toggle is_bookable
    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/toggle-bookable",
        headers=_auth(str(staff_profile_users["staff1_token"])),
        json={"is_bookable": False},
    )

    assert response.status_code == 403


def test_owner_can_toggle_is_bookable(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)

    # Create profile
    response_create = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_create.json()["id"]

    # Owner toggles is_bookable to false
    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/toggle-bookable",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"is_bookable": False},
    )

    assert response.status_code == 200
    assert response.json()["is_bookable"] is False

    # Toggle back to true
    response2 = client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/toggle-bookable",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"is_bookable": True},
    )

    assert response2.status_code == 200
    assert response2.json()["is_bookable"] is True


def test_manager_can_toggle_is_bookable(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)

    # Create profile
    response_create = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_create.json()["id"]

    # Manager toggles is_bookable
    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/toggle-bookable",
        headers=_auth(str(staff_profile_users["manager_token"])),
        json={"is_bookable": False},
    )

    assert response.status_code == 200
    assert response.json()["is_bookable"] is False


def test_nullable_personal_fields_can_be_cleared(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)

    # Create profile with data
    response_create = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_create.json()["id"]

    # Set personal fields
    client.patch(
        f"/salons/{salon.id}/staff-profiles/{profile_id}",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={
            "display_name": "John",
            "phone": "123456",
            "bio": "Expert",
            "photo_url": "https://example.com/photo.jpg",
        },
    )

    # Clear them explicitly with null
    response = client.patch(
        f"/salons/{salon.id}/staff-profiles/{profile_id}",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={
            "display_name": None,
            "phone": None,
            "bio": None,
            "photo_url": None,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["display_name"] is None
    assert payload["phone"] is None
    assert payload["bio"] is None
    assert payload["photo_url"] is None


def test_owner_can_update_any_profile_personal_fields(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)

    # Create profile for staff1
    response_create = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_create.json()["id"]

    # Owner updates staff1's profile
    response = client.patch(
        f"/salons/{salon.id}/staff-profiles/{profile_id}",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"display_name": "Updated by Owner"},
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated by Owner"


# ============================================================================
# Staff-Service Assignment Tests
# ============================================================================


def test_owner_can_assign_service_to_staff(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    service1 = staff_profile_users["service1"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)
    assert isinstance(service1, SalonService)

    # Create staff profile
    response_profile = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_profile.json()["id"]

    # Assign service
    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service1.id}",
        headers=_auth(str(staff_profile_users["owner_token"])),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["staff_profile_id"] == profile_id
    assert payload["salon_service_id"] == str(service1.id)
    assert payload["created_at"]


def test_manager_can_assign_service(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    service1 = staff_profile_users["service1"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)
    assert isinstance(service1, SalonService)

    # Create staff profile
    response_profile = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_profile.json()["id"]

    # Manager assigns service
    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service1.id}",
        headers=_auth(str(staff_profile_users["manager_token"])),
    )

    assert response.status_code == 201


def test_staff_cannot_assign_service(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff2_membership = staff_profile_users["staff2_membership"]
    service1 = staff_profile_users["service1"]
    assert isinstance(salon, Salon)
    assert isinstance(staff2_membership, SalonMembership)
    assert isinstance(service1, SalonService)

    # Create profile for staff2
    response_profile = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff2_membership.id)},
    )
    profile_id = response_profile.json()["id"]

    # Staff2 tries to assign service to another staff
    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service1.id}",
        headers=_auth(str(staff_profile_users["staff2_token"])),
    )

    assert response.status_code == 403


def test_staff_cannot_self_assign_service(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    service1 = staff_profile_users["service1"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)
    assert isinstance(service1, SalonService)

    # Create profile for staff1
    response_profile = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_profile.json()["id"]

    # Staff1 tries to self-assign
    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service1.id}",
        headers=_auth(str(staff_profile_users["staff1_token"])),
    )

    assert response.status_code == 403


def test_duplicate_assignment_returns_409(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    service1 = staff_profile_users["service1"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)
    assert isinstance(service1, SalonService)

    # Create profile
    response_profile = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_profile.json()["id"]

    # First assignment
    response1 = client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service1.id}",
        headers=_auth(str(staff_profile_users["owner_token"])),
    )
    assert response1.status_code == 201

    # Duplicate assignment
    response2 = client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service1.id}",
        headers=_auth(str(staff_profile_users["owner_token"])),
    )
    assert response2.status_code == 409


def test_owner_can_unassign_service(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    service1 = staff_profile_users["service1"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)
    assert isinstance(service1, SalonService)

    # Create profile and assignment
    response_profile = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_profile.json()["id"]

    client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service1.id}",
        headers=_auth(str(staff_profile_users["owner_token"])),
    )

    # Unassign
    response = client.delete(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service1.id}",
        headers=_auth(str(staff_profile_users["owner_token"])),
    )

    assert response.status_code == 204


def test_manager_can_unassign_service(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    service1 = staff_profile_users["service1"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)
    assert isinstance(service1, SalonService)

    # Create profile and assignment
    response_profile = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_profile.json()["id"]

    client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service1.id}",
        headers=_auth(str(staff_profile_users["owner_token"])),
    )

    # Manager unassigns
    response = client.delete(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service1.id}",
        headers=_auth(str(staff_profile_users["manager_token"])),
    )

    assert response.status_code == 204


def test_staff_cannot_unassign_service(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    service1 = staff_profile_users["service1"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)
    assert isinstance(service1, SalonService)

    # Create profile and assignment
    response_profile = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_profile.json()["id"]

    client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service1.id}",
        headers=_auth(str(staff_profile_users["owner_token"])),
    )

    # Staff tries to unassign
    response = client.delete(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service1.id}",
        headers=_auth(str(staff_profile_users["staff1_token"])),
    )

    assert response.status_code == 403


def test_assignment_list_and_read(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    service1 = staff_profile_users["service1"]
    service2 = staff_profile_users["service2"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)
    assert isinstance(service1, SalonService)
    assert isinstance(service2, SalonService)

    # Create profile
    response_profile = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_profile.json()["id"]

    # Assign two services
    client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service1.id}",
        headers=_auth(str(staff_profile_users["owner_token"])),
    )
    client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{service2.id}",
        headers=_auth(str(staff_profile_users["owner_token"])),
    )

    # List assignments (staff can read)
    response = client.get(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services",
        headers=_auth(str(staff_profile_users["staff1_token"])),
    )

    assert response.status_code == 200
    assignments = response.json()
    assert len(assignments) == 2


def test_cross_salon_staff_profile_returns_404(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    """Cannot assign service when staff profile is from another salon."""
    salon = staff_profile_users["salon"]
    service1 = staff_profile_users["service1"]
    assert isinstance(salon, Salon)
    assert isinstance(service1, SalonService)

    # Create another salon with owner and profile
    other_owner, other_token = _create_user(db_session, "other-staff-owner@example.com")
    other_salon = _create_salon(db_session, other_owner, "other-staff")
    other_membership = _add_membership(db_session, other_salon, other_owner, "owner")

    # Create profile in other salon
    response_profile = client.post(
        f"/salons/{other_salon.id}/staff-profiles",
        headers=_auth(other_token),
        json={"membership_id": str(other_membership.id)},
    )
    other_profile_id = response_profile.json()["id"]

    # Try to assign service from first salon to profile from other salon
    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{other_profile_id}/services/{service1.id}",
        headers=_auth(str(staff_profile_users["owner_token"])),
    )

    assert response.status_code == 404


def test_cross_salon_service_returns_404(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    """Cannot assign service from another salon to staff profile."""
    salon = staff_profile_users["salon"]
    staff1_membership = staff_profile_users["staff1_membership"]
    assert isinstance(salon, Salon)
    assert isinstance(staff1_membership, SalonMembership)

    # Create profile in first salon
    response_profile = client.post(
        f"/salons/{salon.id}/staff-profiles",
        headers=_auth(str(staff_profile_users["owner_token"])),
        json={"membership_id": str(staff1_membership.id)},
    )
    profile_id = response_profile.json()["id"]

    # Create another salon with service
    other_owner, other_token = _create_user(db_session, "other-service-owner@example.com")
    other_salon = _create_salon(db_session, other_owner, "other-service")
    other_service = _create_service(db_session, other_salon, "Other Service")

    # Try to assign service from other salon
    response = client.post(
        f"/salons/{salon.id}/staff-profiles/{profile_id}/services/{other_service.id}",
        headers=_auth(str(staff_profile_users["owner_token"])),
    )

    assert response.status_code == 404


def test_service_profile_tenant_mismatch_rejected(
    db_session: Session, staff_profile_users: dict[str, object]
) -> None:
    """Service and profile from different salons cannot be assigned even via direct DB."""
    # Create two separate salons with their own resources
    owner1, token1 = _create_user(db_session, "salon1-owner@example.com")
    salon1 = _create_salon(db_session, owner1, "salon1")
    membership1 = _add_membership(db_session, salon1, owner1, "owner")

    owner2, token2 = _create_user(db_session, "salon2-owner@example.com")
    salon2 = _create_salon(db_session, owner2, "salon2")
    service2 = _create_service(db_session, salon2, "Salon2 Service")

    # Create profile in salon1
    response_profile = client.post(
        f"/salons/{salon1.id}/staff-profiles",
        headers=_auth(token1),
        json={"membership_id": str(membership1.id)},
    )
    profile1_id = response_profile.json()["id"]

    # Try to assign service from salon2 to profile from salon1
    # This should fail because of cross-salon invariant
    response = client.post(
        f"/salons/{salon1.id}/staff-profiles/{profile1_id}/services/{service2.id}",
        headers=_auth(token1),
    )

    assert response.status_code == 404
