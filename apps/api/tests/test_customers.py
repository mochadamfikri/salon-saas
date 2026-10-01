"""P2-E Salon Customer API contract tests."""

import pytest
from app.core.security import hash_password
from app.main import app
from app.models import Salon, SalonMembership, User
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


def _add_membership(db_session: Session, salon: Salon, user: User, role: str) -> SalonMembership:
    membership = SalonMembership(salon_id=salon.id, user_id=user.id, role=role, status="active")
    db_session.add(membership)
    db_session.commit()
    return membership


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _customer_url(salon: Salon) -> str:
    return f"/salons/{salon.id}/customers"


@pytest.fixture
def customer_setup(db_session: Session) -> dict[str, object]:
    owner, owner_token = _create_user(db_session, "customer-owner@example.com")
    manager, manager_token = _create_user(db_session, "customer-manager@example.com")
    staff, staff_token = _create_user(db_session, "customer-staff@example.com")
    salon = _create_salon(db_session, owner, "customers")
    _add_membership(db_session, salon, owner, "owner")
    _add_membership(db_session, salon, manager, "manager")
    _add_membership(db_session, salon, staff, "staff")
    return {
        "salon": salon,
        "owner_token": owner_token,
        "manager_token": manager_token,
        "staff_token": staff_token,
    }


@pytest.mark.parametrize("token_key", ["owner_token", "manager_token", "staff_token"])
def test_all_roles_create_read_and_update_customer(
    customer_setup: dict[str, object], token_key: str
) -> None:
    salon = customer_setup["salon"]
    assert isinstance(salon, Salon)
    token = str(customer_setup[token_key])

    created = client.post(
        _customer_url(salon),
        headers=_auth(token),
        json={"full_name": "Customer One", "phone": "081234"},
    )
    assert created.status_code == 201
    customer_id = created.json()["id"]

    listed = client.get(_customer_url(salon), headers=_auth(token))
    assert listed.status_code == 200
    assert [customer["id"] for customer in listed.json()] == [customer_id]

    detail = client.get(f"{_customer_url(salon)}/{customer_id}", headers=_auth(token))
    assert detail.status_code == 200
    assert detail.json()["full_name"] == "Customer One"

    updated = client.patch(
        f"{_customer_url(salon)}/{customer_id}",
        headers=_auth(token),
        json={"notes": "Walk-in follow-up"},
    )
    assert updated.status_code == 200
    assert updated.json()["notes"] == "Walk-in follow-up"


def test_walk_in_customer_accepts_full_name_only(customer_setup: dict[str, object]) -> None:
    salon = customer_setup["salon"]
    assert isinstance(salon, Salon)
    response = client.post(
        _customer_url(salon),
        headers=_auth(str(customer_setup["staff_token"])),
        json={"full_name": "Walk In"},
    )
    assert response.status_code == 201
    assert response.json()["email"] is None
    assert response.json()["phone"] is None
    assert response.json()["notes"] is None


def test_customer_normalization_and_full_name_validation(customer_setup: dict[str, object]) -> None:
    salon = customer_setup["salon"]
    assert isinstance(salon, Salon)
    headers = _auth(str(customer_setup["owner_token"]))

    created = client.post(
        _customer_url(salon),
        headers=headers,
        json={
            "full_name": "  Jane Customer  ",
            "email": "  JANE@EXAMPLE.COM  ",
            "phone": "  0812-3456  ",
        },
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["full_name"] == "Jane Customer"
    assert payload["email"] == "jane@example.com"
    assert payload["phone"] == "0812-3456"

    blank = client.post(_customer_url(salon), headers=headers, json={"full_name": "   "})
    assert blank.status_code == 422

    null_name = client.post(_customer_url(salon), headers=headers, json={"full_name": None})
    assert null_name.status_code == 422


def test_nullable_fields_clear_and_omitted_fields_remain_unchanged(
    customer_setup: dict[str, object],
) -> None:
    salon = customer_setup["salon"]
    assert isinstance(salon, Salon)
    headers = _auth(str(customer_setup["manager_token"]))
    created = client.post(
        _customer_url(salon),
        headers=headers,
        json={
            "full_name": "Customer Clear",
            "email": "clear@example.com",
            "phone": "0812345",
            "notes": "keep name",
        },
    )
    customer_id = created.json()["id"]

    cleared = client.patch(
        f"{_customer_url(salon)}/{customer_id}",
        headers=headers,
        json={"email": None, "phone": None, "notes": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["email"] is None
    assert cleared.json()["phone"] is None
    assert cleared.json()["notes"] is None
    assert cleared.json()["full_name"] == "Customer Clear"

    unchanged = client.patch(
        f"{_customer_url(salon)}/{customer_id}", headers=headers, json={"notes": "new note"}
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["full_name"] == "Customer Clear"
    assert unchanged.json()["email"] is None
    assert unchanged.json()["phone"] is None
    assert unchanged.json()["notes"] == "new note"


def test_patch_rejects_null_or_blank_full_name(customer_setup: dict[str, object]) -> None:
    salon = customer_setup["salon"]
    assert isinstance(salon, Salon)
    headers = _auth(str(customer_setup["owner_token"]))
    created = client.post(_customer_url(salon), headers=headers, json={"full_name": "Customer"})
    customer_id = created.json()["id"]

    null_name = client.patch(
        f"{_customer_url(salon)}/{customer_id}", headers=headers, json={"full_name": None}
    )
    assert null_name.status_code == 422
    blank_name = client.patch(
        f"{_customer_url(salon)}/{customer_id}", headers=headers, json={"full_name": "  "}
    )
    assert blank_name.status_code == 422


def test_duplicate_email_and_phone_are_allowed(customer_setup: dict[str, object]) -> None:
    salon = customer_setup["salon"]
    assert isinstance(salon, Salon)
    headers = _auth(str(customer_setup["owner_token"]))
    first = client.post(
        _customer_url(salon),
        headers=headers,
        json={"full_name": "First", "email": "same@example.com", "phone": "0812"},
    )
    second = client.post(
        _customer_url(salon),
        headers=headers,
        json={"full_name": "Second", "email": "same@example.com", "phone": "0812"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


def test_customer_tenant_isolation_and_no_data_leak(
    db_session: Session, customer_setup: dict[str, object]
) -> None:
    salon = customer_setup["salon"]
    assert isinstance(salon, Salon)
    headers = _auth(str(customer_setup["owner_token"]))
    created = client.post(
        _customer_url(salon), headers=headers, json={"full_name": "Private Customer"}
    )
    customer_id = created.json()["id"]

    other_owner, other_token = _create_user(db_session, "customer-other-owner@example.com")
    other_salon = _create_salon(db_session, other_owner, "other-customers")
    _add_membership(db_session, other_salon, other_owner, "owner")
    other_headers = _auth(other_token)

    assert (
        client.get(f"{_customer_url(other_salon)}/{customer_id}", headers=other_headers).status_code
        == 404
    )
    assert (
        client.patch(
            f"{_customer_url(other_salon)}/{customer_id}",
            headers=other_headers,
            json={"notes": "attack"},
        ).status_code
        == 404
    )
    assert client.get(_customer_url(other_salon), headers=other_headers).json() == []


def test_salon_ownership_spoofing_is_rejected(customer_setup: dict[str, object]) -> None:
    salon = customer_setup["salon"]
    assert isinstance(salon, Salon)
    headers = _auth(str(customer_setup["owner_token"]))

    response = client.post(
        _customer_url(salon),
        headers=headers,
        json={"full_name": "Spoof Attempt", "salon_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 422


def test_customer_delete_endpoint_is_absent(customer_setup: dict[str, object]) -> None:
    salon = customer_setup["salon"]
    assert isinstance(salon, Salon)
    response = client.delete(
        _customer_url(salon), headers=_auth(str(customer_setup["owner_token"]))
    )
    assert response.status_code == 405
