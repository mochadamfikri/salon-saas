"""P2-B Service Catalog API contract and tenant-isolation tests."""

from decimal import Decimal
from uuid import uuid4

import pytest
from app.core.security import hash_password
from app.main import app
from app.models import Salon, SalonMembership, SalonService, User
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
) -> None:
    db_session.add(SalonMembership(salon_id=salon.id, user_id=user.id, role=role, status=status))
    db_session.commit()


@pytest.fixture
def salon_users(db_session: Session) -> dict[str, object]:
    owner, owner_token = _create_user(db_session, "service-owner@example.com")
    manager, manager_token = _create_user(db_session, "service-manager@example.com")
    staff, staff_token = _create_user(db_session, "service-staff@example.com")
    suspended, suspended_token = _create_user(db_session, "service-suspended@example.com")
    salon = _create_salon(db_session, owner, "services")
    _add_membership(db_session, salon, owner, "owner")
    _add_membership(db_session, salon, manager, "manager")
    _add_membership(db_session, salon, staff, "staff")
    _add_membership(db_session, salon, suspended, "staff", "suspended")
    return {
        "salon": salon,
        "owner_token": owner_token,
        "manager_token": manager_token,
        "staff_token": staff_token,
        "suspended_token": suspended_token,
    }


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_owner_creates_service_with_contract_defaults(
    db_session: Session, salon_users: dict[str, object]
) -> None:
    salon = salon_users["salon"]
    assert isinstance(salon, Salon)
    response = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={"name": "Haircut", "duration_minutes": 45, "price_amount": "75000.00"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["salon_id"] == str(salon.id)
    assert payload["name"] == "Haircut"
    assert payload["currency"] == "IDR"
    assert payload["price_amount"] == "75000.00"
    assert payload["is_active"] is True
    assert payload["description"] is None
    assert payload["category"] is None
    assert payload["created_at"]
    assert payload["updated_at"]
    saved = db_session.get(SalonService, payload["id"])
    assert saved is not None
    assert saved.price_amount == Decimal("75000.00")


def test_manager_creates_service_with_optional_fields(
    db_session: Session, salon_users: dict[str, object]
) -> None:
    salon = salon_users["salon"]
    assert isinstance(salon, Salon)
    response = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["manager_token"])),
        json={
            "name": "Full Facial Treatment",
            "description": "Deep cleanse and massage",
            "category": "Facial",
            "duration_minutes": 90,
            "price_amount": "150000.50",
            "currency": "IDR",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Full Facial Treatment"
    assert payload["description"] == "Deep cleanse and massage"
    assert payload["category"] == "Facial"
    assert payload["duration_minutes"] == 90
    assert payload["price_amount"] == "150000.50"


def test_staff_cannot_create_service(salon_users: dict[str, object]) -> None:
    salon = salon_users["salon"]
    assert isinstance(salon, Salon)
    response = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["staff_token"])),
        json={"name": "Forbidden Service", "duration_minutes": 30, "price_amount": "10000.00"},
    )
    assert response.status_code == 403


def test_owner_and_manager_can_update_service(salon_users: dict[str, object]) -> None:
    salon = salon_users["salon"]
    assert isinstance(salon, Salon)
    created = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={"name": "Old Haircut", "duration_minutes": 30, "price_amount": "50000.00"},
    ).json()

    patch_by_owner = client.patch(
        f"/salons/{salon.id}/services/{created['id']}",
        headers=_auth(str(salon_users["owner_token"])),
        json={"name": "Owner Updated Haircut", "price_amount": "60000.00"},
    )
    assert patch_by_owner.status_code == 200
    assert patch_by_owner.json()["name"] == "Owner Updated Haircut"
    assert patch_by_owner.json()["price_amount"] == "60000.00"

    patch_by_manager = client.patch(
        f"/salons/{salon.id}/services/{created['id']}",
        headers=_auth(str(salon_users["manager_token"])),
        json={"category": "Styling", "duration_minutes": 40},
    )
    assert patch_by_manager.status_code == 200
    assert patch_by_manager.json()["category"] == "Styling"
    assert patch_by_manager.json()["duration_minutes"] == 40


def test_staff_cannot_update_service(salon_users: dict[str, object]) -> None:
    salon = salon_users["salon"]
    assert isinstance(salon, Salon)
    created = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={"name": "Haircut", "duration_minutes": 30, "price_amount": "50000.00"},
    ).json()

    response = client.patch(
        f"/salons/{salon.id}/services/{created['id']}",
        headers=_auth(str(salon_users["staff_token"])),
        json={"name": "Malicious Name"},
    )
    assert response.status_code == 403


def test_owner_and_manager_activate_deactivate_lifecycle(salon_users: dict[str, object]) -> None:
    salon = salon_users["salon"]
    assert isinstance(salon, Salon)
    created = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={"name": "Hair Coloring", "duration_minutes": 60, "price_amount": "200000.00"},
    ).json()
    assert created["is_active"] is True

    deact = client.post(
        f"/salons/{salon.id}/services/{created['id']}/deactivate",
        headers=_auth(str(salon_users["manager_token"])),
    )
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False

    act = client.post(
        f"/salons/{salon.id}/services/{created['id']}/activate",
        headers=_auth(str(salon_users["owner_token"])),
    )
    assert act.status_code == 200
    assert act.json()["is_active"] is True


def test_staff_cannot_activate_or_deactivate(salon_users: dict[str, object]) -> None:
    salon = salon_users["salon"]
    assert isinstance(salon, Salon)
    created = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={"name": "Hair Wash", "duration_minutes": 15, "price_amount": "25000.00"},
    ).json()

    resp_deact = client.post(
        f"/salons/{salon.id}/services/{created['id']}/deactivate",
        headers=_auth(str(salon_users["staff_token"])),
    )
    assert resp_deact.status_code == 403

    resp_act = client.post(
        f"/salons/{salon.id}/services/{created['id']}/activate",
        headers=_auth(str(salon_users["staff_token"])),
    )
    assert resp_act.status_code == 403


def test_staff_can_read_service_and_list(salon_users: dict[str, object]) -> None:
    salon = salon_users["salon"]
    assert isinstance(salon, Salon)
    created = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={"name": "Perm", "duration_minutes": 120, "price_amount": "300000.00"},
    ).json()

    get_resp = client.get(
        f"/salons/{salon.id}/services/{created['id']}",
        headers=_auth(str(salon_users["staff_token"])),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == created["id"]

    list_resp = client.get(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["staff_token"])),
    )
    assert list_resp.status_code == 200
    assert any(s["id"] == created["id"] for s in list_resp.json())


def test_list_and_get_cross_tenant_isolation(
    db_session: Session, salon_users: dict[str, object]
) -> None:
    salon_a = salon_users["salon"]
    assert isinstance(salon_a, Salon)
    service_a = client.post(
        f"/salons/{salon_a.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={"name": "Tenant A Exclusive", "duration_minutes": 20, "price_amount": "10000.00"},
    ).json()

    # Create second salon with different owner
    owner_b, owner_b_token = _create_user(db_session, "tenant-b-owner@example.com")
    salon_b = _create_salon(db_session, owner_b, "tenant-b")
    _add_membership(db_session, salon_b, owner_b, "owner")

    # Salon B owner trying to get Salon A's service under Salon B's path returns 404
    resp_b_look_a = client.get(
        f"/salons/{salon_b.id}/services/{service_a['id']}",
        headers=_auth(owner_b_token),
    )
    assert resp_b_look_a.status_code == 404

    # Salon B owner trying to access Salon A's path directly returns 404 (Phase 1 tenant hiding)
    resp_b_path_a = client.get(
        f"/salons/{salon_a.id}/services/{service_a['id']}",
        headers=_auth(owner_b_token),
    )
    assert resp_b_path_a.status_code == 404

    # Salon B service listing must not include Salon A's service
    list_b = client.get(
        f"/salons/{salon_b.id}/services",
        headers=_auth(owner_b_token),
    ).json()
    assert all(item["id"] != service_a["id"] for item in list_b)


def test_suspended_membership_denied(salon_users: dict[str, object]) -> None:
    salon = salon_users["salon"]
    assert isinstance(salon, Salon)
    response = client.get(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["suspended_token"])),
    )
    # Suspended membership gets 404 per Phase 1 tenant context design
    assert response.status_code == 404


def test_invalid_duration_and_negative_price_rejected(salon_users: dict[str, object]) -> None:
    salon = salon_users["salon"]
    assert isinstance(salon, Salon)

    # Zero duration
    res1 = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={"name": "Bad Duration", "duration_minutes": 0, "price_amount": "50000.00"},
    )
    assert res1.status_code == 422

    # Negative duration
    res2 = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={"name": "Negative Duration", "duration_minutes": -10, "price_amount": "50000.00"},
    )
    assert res2.status_code == 422

    # Negative price
    res3 = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={"name": "Negative Price", "duration_minutes": 30, "price_amount": "-10.00"},
    )
    assert res3.status_code == 422


def test_client_cannot_override_salon_id(
    db_session: Session, salon_users: dict[str, object]
) -> None:
    salon = salon_users["salon"]
    assert isinstance(salon, Salon)
    fake_salon_id = uuid4()

    response = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={
            "name": "Spoofed Salon ID",
            "salon_id": str(fake_salon_id),
            "duration_minutes": 30,
            "price_amount": "50000.00",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["salon_id"] == str(salon.id)
    assert payload["salon_id"] != str(fake_salon_id)


def test_patch_can_clear_nullable_fields_with_explicit_null(salon_users: dict[str, object]) -> None:
    """Nullable fields (description, category) can be cleared with explicit null."""
    salon = salon_users["salon"]
    assert isinstance(salon, Salon)

    # Create service with description and category
    created = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={
            "name": "Service With Details",
            "description": "Original description",
            "category": "Original category",
            "duration_minutes": 30,
            "price_amount": "50000.00",
        },
    ).json()
    assert created["description"] == "Original description"
    assert created["category"] == "Original category"

    # Clear description with explicit null
    clear_desc = client.patch(
        f"/salons/{salon.id}/services/{created['id']}",
        headers=_auth(str(salon_users["owner_token"])),
        json={"description": None},
    )
    assert clear_desc.status_code == 200
    assert clear_desc.json()["description"] is None
    assert clear_desc.json()["category"] == "Original category"  # unchanged

    # Clear category with explicit null
    clear_cat = client.patch(
        f"/salons/{salon.id}/services/{created['id']}",
        headers=_auth(str(salon_users["owner_token"])),
        json={"category": None},
    )
    assert clear_cat.status_code == 200
    assert clear_cat.json()["category"] is None


def test_patch_rejects_null_for_non_nullable_fields(salon_users: dict[str, object]) -> None:
    """Non-nullable fields (name, duration, price, currency) reject explicit null with 422."""
    salon = salon_users["salon"]
    assert isinstance(salon, Salon)

    created = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={"name": "Original Name", "duration_minutes": 30, "price_amount": "50000.00"},
    ).json()

    # name null -> 422
    resp_name = client.patch(
        f"/salons/{salon.id}/services/{created['id']}",
        headers=_auth(str(salon_users["owner_token"])),
        json={"name": None},
    )
    assert resp_name.status_code == 422

    # duration_minutes null -> 422
    resp_duration = client.patch(
        f"/salons/{salon.id}/services/{created['id']}",
        headers=_auth(str(salon_users["owner_token"])),
        json={"duration_minutes": None},
    )
    assert resp_duration.status_code == 422

    # price_amount null -> 422
    resp_price = client.patch(
        f"/salons/{salon.id}/services/{created['id']}",
        headers=_auth(str(salon_users["owner_token"])),
        json={"price_amount": None},
    )
    assert resp_price.status_code == 422

    # currency null -> 422
    resp_currency = client.patch(
        f"/salons/{salon.id}/services/{created['id']}",
        headers=_auth(str(salon_users["owner_token"])),
        json={"currency": None},
    )
    assert resp_currency.status_code == 422


def test_oversized_decimal_rejected(salon_users: dict[str, object]) -> None:
    """Price exceeding Numeric(12,2) rejected with 422 before reaching DB."""
    salon = salon_users["salon"]
    assert isinstance(salon, Salon)

    # Create: price > 12 digits total (10 integer + 2 decimal) -> 422
    resp_create = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={
            "name": "Oversized Price",
            "duration_minutes": 30,
            "price_amount": "12345678901.00",  # 13 digits total
        },
    )
    assert resp_create.status_code == 422

    # PATCH: same constraint
    created = client.post(
        f"/salons/{salon.id}/services",
        headers=_auth(str(salon_users["owner_token"])),
        json={"name": "Normal Service", "duration_minutes": 30, "price_amount": "50000.00"},
    ).json()

    resp_patch = client.patch(
        f"/salons/{salon.id}/services/{created['id']}",
        headers=_auth(str(salon_users["owner_token"])),
        json={"price_amount": "99999999999.99"},  # 13 digits total
    )
    assert resp_patch.status_code == 422
