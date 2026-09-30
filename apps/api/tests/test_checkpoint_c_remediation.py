"""Auditor-required Checkpoint C RBAC, isolation, and slug remediation tests."""

from typing import Any

import pytest
from app.core.security import hash_password
from app.main import app
from app.models import SalonMembership, User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

client = TestClient(app)


def _create_user_and_token(db: Session, email: str) -> tuple[User, str]:
    user = User(email=email, password_hash=hash_password("SecurePass123"), is_active=True)
    db.add(user)
    db.commit()
    response = client.post("/auth/login", json={"email": email, "password": "SecurePass123"})
    assert response.status_code == 200
    return user, response.json()["access_token"]


def _create_salon(token: str, name: str = "Salon Alpha", slug: str | None = None) -> dict[str, Any]:
    payload: dict[str, str] = {"name": name}
    if slug is not None:
        payload["slug"] = slug
    response = client.post("/salons", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _add_membership(
    db: Session, salon_id: str, role: str, email: str
) -> tuple[User, SalonMembership, str]:
    user, token = _create_user_and_token(db, email)
    membership = SalonMembership(salon_id=salon_id, user_id=user.id, role=role, status="active")
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return user, membership, token


@pytest.fixture
def owned_salon(db_session: Session) -> tuple[dict[str, Any], str, Session]:
    _, owner_token = _create_user_and_token(db_session, "owner-rbac@example.com")
    salon = _create_salon(owner_token, slug="owner-rbac-salon")
    return salon, owner_token, db_session


def test_owner_can_list_members(owned_salon: tuple[dict[str, Any], str, Session]) -> None:
    salon, owner_token, _ = owned_salon
    response = client.get(
        f"/salons/{salon['id']}/members", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert response.status_code == 200


def test_manager_can_list_members(owned_salon: tuple[dict[str, Any], str, Session]) -> None:
    salon, _, db = owned_salon
    _, _, manager_token = _add_membership(db, salon["id"], "manager", "manager-list@example.com")
    response = client.get(
        f"/salons/{salon['id']}/members", headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == 200


def test_staff_cannot_list_members(owned_salon: tuple[dict[str, Any], str, Session]) -> None:
    salon, _, db = owned_salon
    _, _, staff_token = _add_membership(db, salon["id"], "staff", "staff-list@example.com")
    response = client.get(
        f"/salons/{salon['id']}/members", headers={"Authorization": f"Bearer {staff_token}"}
    )
    assert response.status_code == 403


def test_manager_can_demote_staff_only(owned_salon: tuple[dict[str, Any], str, Session]) -> None:
    salon, _, db = owned_salon
    _, _, manager_token = _add_membership(db, salon["id"], "manager", "manager-manage@example.com")
    _, staff_membership, _ = _add_membership(db, salon["id"], "staff", "staff-manage@example.com")
    response = client.patch(
        f"/salons/{salon['id']}/members/{staff_membership.id}",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"role": "staff"},
    )
    assert response.status_code == 200


def test_manager_cannot_promote_staff_to_manager(
    owned_salon: tuple[dict[str, Any], str, Session],
) -> None:
    salon, _, db = owned_salon
    _, _, manager_token = _add_membership(db, salon["id"], "manager", "manager-promote@example.com")
    _, staff_membership, _ = _add_membership(db, salon["id"], "staff", "staff-promote@example.com")
    response = client.patch(
        f"/salons/{salon['id']}/members/{staff_membership.id}",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"role": "manager"},
    )
    assert response.status_code == 403


def test_manager_cannot_manage_manager(owned_salon: tuple[dict[str, Any], str, Session]) -> None:
    salon, _, db = owned_salon
    _, _, actor_token = _add_membership(db, salon["id"], "manager", "manager-actor@example.com")
    _, target_membership, _ = _add_membership(
        db, salon["id"], "manager", "manager-target@example.com"
    )
    response = client.delete(
        f"/salons/{salon['id']}/members/{target_membership.id}",
        headers={"Authorization": f"Bearer {actor_token}"},
    )
    assert response.status_code == 403


def test_non_member_gets_404_for_other_salon(db_session: Session) -> None:
    _, owner_token = _create_user_and_token(db_session, "owner-a@example.com")
    salon_a = _create_salon(owner_token, slug="salon-a-isolated")
    _, other_token = _create_user_and_token(db_session, "owner-b@example.com")
    salon_b = _create_salon(other_token, slug="salon-b-isolated")
    assert salon_a["id"] != salon_b["id"]
    response = client.get(
        f"/salons/{salon_b['id']}/members", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Salon not found"


def test_create_salon_without_slug_generates_safe_unique_slug(db_session: Session) -> None:
    _, token = _create_user_and_token(db_session, "slug-auto@example.com")
    first = _create_salon(token, name="Beauty & Wellness Studio")
    second = _create_salon(token, name="Beauty & Wellness Studio")
    assert first["slug"] == "beauty-wellness-studio"
    assert second["slug"] == "beauty-wellness-studio-2"


def test_suspended_member_gets_same_404_as_non_member(
    owned_salon: tuple[dict[str, Any], str, Session],
) -> None:
    salon, _, db = owned_salon
    _, membership, suspended_token = _add_membership(
        db, salon["id"], "staff", "suspended-list@example.com"
    )
    membership.status = "suspended"
    db.commit()

    response = client.get(
        f"/salons/{salon['id']}/members",
        headers={"Authorization": f"Bearer {suspended_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Salon not found"


def test_manager_can_suspend_staff(owned_salon: tuple[dict[str, Any], str, Session]) -> None:
    salon, _, db = owned_salon
    _, _, manager_token = _add_membership(db, salon["id"], "manager", "manager-suspend@example.com")
    _, staff_membership, _ = _add_membership(db, salon["id"], "staff", "staff-suspend@example.com")

    response = client.patch(
        f"/salons/{salon['id']}/members/{staff_membership.id}",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"status": "suspended"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "suspended"
    db.refresh(staff_membership)
    assert staff_membership.status == "suspended"


def test_manager_cannot_suspend_manager(owned_salon: tuple[dict[str, Any], str, Session]) -> None:
    salon, _, db = owned_salon
    _, _, actor_token = _add_membership(
        db, salon["id"], "manager", "manager-suspend-actor@example.com"
    )
    _, target_membership, _ = _add_membership(
        db, salon["id"], "manager", "manager-suspend-target@example.com"
    )

    response = client.patch(
        f"/salons/{salon['id']}/members/{target_membership.id}",
        headers={"Authorization": f"Bearer {actor_token}"},
        json={"status": "suspended"},
    )

    assert response.status_code == 403


def test_staff_cannot_suspend_staff(owned_salon: tuple[dict[str, Any], str, Session]) -> None:
    salon, _, db = owned_salon
    _, _, staff_actor_token = _add_membership(
        db, salon["id"], "staff", "staff-suspend-actor@example.com"
    )
    _, target_membership, _ = _add_membership(
        db, salon["id"], "staff", "staff-suspend-target@example.com"
    )

    response = client.patch(
        f"/salons/{salon['id']}/members/{target_membership.id}",
        headers={"Authorization": f"Bearer {staff_actor_token}"},
        json={"status": "suspended"},
    )

    assert response.status_code == 403


def test_owner_can_suspend_manager(owned_salon: tuple[dict[str, Any], str, Session]) -> None:
    salon, owner_token, db = owned_salon
    _, manager_membership, _ = _add_membership(
        db, salon["id"], "manager", "owner-suspend-manager@example.com"
    )

    response = client.patch(
        f"/salons/{salon['id']}/members/{manager_membership.id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"status": "suspended"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "suspended"


def test_owner_cannot_suspend_owner(owned_salon: tuple[dict[str, Any], str, Session]) -> None:
    salon, owner_token, db = owned_salon
    owner_membership = (
        db.query(SalonMembership)
        .filter(SalonMembership.salon_id == salon["id"], SalonMembership.role == "owner")
        .one()
    )

    response = client.patch(
        f"/salons/{salon['id']}/members/{owner_membership.id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"status": "suspended"},
    )

    assert response.status_code == 403


def test_cross_tenant_membership_id_is_hidden(
    owned_salon: tuple[dict[str, Any], str, Session],
) -> None:
    salon, owner_token, db = owned_salon
    other_user, other_token = _create_user_and_token(db, "other-tenant-owner@example.com")
    other_salon = _create_salon(other_token, slug="other-membership-salon")
    _, other_membership, _ = _add_membership(
        db, other_salon["id"], "staff", "other-membership-staff@example.com"
    )

    response = client.patch(
        f"/salons/{salon['id']}/members/{other_membership.id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"status": "suspended"},
    )

    assert response.status_code == 404


@pytest.mark.parametrize("slug", ["admin", "api", "auth", "docs", "health", "me", "salons"])
def test_reserved_slug_is_rejected(db_session: Session, slug: str) -> None:
    _, token = _create_user_and_token(db_session, f"reserved-{slug}@example.com")
    response = client.post(
        "/salons",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Reserved Test", "slug": slug},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("slug", ["Bad Slug", "--bad", "a", "valid_underscore"])
def test_invalid_explicit_slug_is_rejected(db_session: Session, slug: str) -> None:
    _, token = _create_user_and_token(db_session, f"invalid-{slug.replace(' ', '-')}@example.com")
    response = client.post(
        "/salons",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Invalid Slug", "slug": slug},
    )
    assert response.status_code == 422
