"""Test salon creation, tenant context, RBAC, and member management."""

import uuid

import pytest
from app.core.security import hash_password
from app.main import app
from app.models import Salon, SalonMembership, User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

client = TestClient(app)


@pytest.fixture
def auth_user(db_session: Session) -> tuple[User, str]:
    """Create authenticated user and return access token."""
    user = User(
        email="owner@example.com",
        password_hash=hash_password("SecurePass123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Login to get token
    response = client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "SecurePass123"},
    )
    access_token = response.json()["access_token"]
    return user, access_token


def test_create_salon_success(db_session: Session, auth_user: tuple[User, str]):
    """Test authenticated user can create salon and becomes OWNER."""
    user, token = auth_user

    response = client.post(
        "/salons",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Beauty Salon", "slug": "beauty-salon"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Beauty Salon"
    assert data["slug"] == "beauty-salon"
    assert data["status"] == "onboarding"
    assert "id" in data

    # Verify salon created in DB
    salon = db_session.query(Salon).filter(Salon.slug == "beauty-salon").first()
    assert salon is not None
    assert salon.created_by_user_id == user.id

    # Verify OWNER membership created
    membership = (
        db_session.query(SalonMembership)
        .filter(SalonMembership.salon_id == salon.id, SalonMembership.user_id == user.id)
        .first()
    )
    assert membership is not None
    assert membership.role == "owner"
    assert membership.status == "active"


def test_create_salon_duplicate_slug(db_session: Session, auth_user: tuple[User, str]):
    """Test duplicate salon slug is rejected."""
    user, token = auth_user

    # Create first salon
    client.post(
        "/salons",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "First Salon", "slug": "test-salon"},
    )

    # Try duplicate slug
    response = client.post(
        "/salons",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Second Salon", "slug": "test-salon"},
    )

    assert response.status_code == 400
    assert "slug" in response.json()["detail"].lower()


def test_create_salon_unauthenticated():
    """Test creating salon without auth fails."""
    response = client.post("/salons", json={"name": "Fail Salon", "slug": "fail-salon"})

    assert response.status_code == 401


def test_get_my_salons(db_session: Session, auth_user: tuple[User, str]):
    """Test user can list their salon memberships."""
    user, token = auth_user

    # Create two salons
    client.post(
        "/salons",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Salon A", "slug": "salon-a"},
    )
    client.post(
        "/salons",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Salon B", "slug": "salon-b"},
    )

    # Get user's salons
    response = client.get("/me/salons", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["salon"]["name"] in ["Salon A", "Salon B"]
    assert data[0]["role"] == "owner"


def test_get_salon_members(db_session: Session, auth_user: tuple[User, str]):
    """Test owner can list salon members."""
    user, token = auth_user

    # Create salon
    create_response = client.post(
        "/salons",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Test Salon", "slug": "test-salon"},
    )
    salon_id = create_response.json()["id"]

    # Get members
    response = client.get(
        f"/salons/{salon_id}/members", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    members = response.json()
    assert len(members) == 1
    assert members[0]["role"] == "owner"
    assert members[0]["user"]["email"] == "owner@example.com"


def test_update_member_role_as_owner(db_session: Session, auth_user: tuple[User, str]):
    """Test owner can update member role."""
    user, token = auth_user

    # Create salon
    create_response = client.post(
        "/salons",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Test Salon", "slug": "test-salon"},
    )
    salon_id = create_response.json()["id"]

    # Add manager member manually
    manager = User(
        email="manager@example.com",
        password_hash=hash_password("Pass123"),
        is_active=True,
    )
    db_session.add(manager)
    db_session.commit()

    membership = SalonMembership(
        salon_id=uuid.UUID(salon_id),
        user_id=manager.id,
        role="manager",
        status="active",
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)

    # Update to staff
    response = client.patch(
        f"/salons/{salon_id}/members/{membership.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "staff"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "staff"


def test_cannot_update_owner_role(db_session: Session, auth_user: tuple[User, str]):
    """Test owner role cannot be changed."""
    user, token = auth_user

    # Create salon
    create_response = client.post(
        "/salons",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Test Salon", "slug": "test-salon"},
    )
    salon_id = create_response.json()["id"]

    # Get owner membership
    membership = (
        db_session.query(SalonMembership)
        .filter(
            SalonMembership.salon_id == uuid.UUID(salon_id),
            SalonMembership.user_id == user.id,
        )
        .first()
    )
    assert membership is not None

    # Try to change owner role
    response = client.patch(
        f"/salons/{salon_id}/members/{membership.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "manager"},
    )

    assert response.status_code == 403
    assert "owner" in response.json()["detail"].lower()


def test_remove_member_as_owner(db_session: Session, auth_user: tuple[User, str]):
    """Test owner can remove non-owner members."""
    user, token = auth_user

    # Create salon
    create_response = client.post(
        "/salons",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Test Salon", "slug": "test-salon"},
    )
    salon_id = create_response.json()["id"]

    # Add staff
    staff = User(
        email="staff@example.com",
        password_hash=hash_password("Pass123"),
        is_active=True,
    )
    db_session.add(staff)
    db_session.commit()

    membership = SalonMembership(
        salon_id=uuid.UUID(salon_id),
        user_id=staff.id,
        role="staff",
        status="active",
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)

    # Remove member
    response = client.delete(
        f"/salons/{salon_id}/members/{membership.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    # Verify membership removed
    removed = db_session.get(SalonMembership, membership.id)
    assert removed is None


def test_cannot_access_other_salon(db_session: Session, auth_user: tuple[User, str]):
    """Test cross-tenant protection: cannot access another salon's data."""
    user, token = auth_user

    # Create salon owned by auth_user
    create_response = client.post(
        "/salons",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "My Salon", "slug": "my-salon"},
    )
    assert create_response.status_code == 201

    # Create another user and their salon
    other_user = User(
        email="other@example.com",
        password_hash=hash_password("Pass123"),
        is_active=True,
    )
    db_session.add(other_user)
    db_session.commit()

    other_salon = Salon(
        name="Other Salon",
        slug="other-salon",
        status="active",
        created_by_user_id=other_user.id,
    )
    db_session.add(other_salon)
    db_session.commit()

    other_membership = SalonMembership(
        salon_id=other_salon.id,
        user_id=other_user.id,
        role="owner",
        status="active",
    )
    db_session.add(other_membership)
    db_session.commit()

    # Try to access other salon's members
    response = client.get(
        f"/salons/{other_salon.id}/members",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "access" in response.json()["detail"].lower()
