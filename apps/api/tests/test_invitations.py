"""Comprehensive invitation lifecycle, RBAC, and security tests."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.security import hash_password
from app.core.tokens import hash_token
from app.main import app
from app.models import SalonInvitation, SalonMembership, User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

client = TestClient(app)


def _create_user_and_login(db: Session, email: str) -> tuple[User, str]:
    """Helper: create user and return access token."""
    user = User(email=email, password_hash=hash_password("SecurePass123"), is_active=True)
    db.add(user)
    db.commit()
    response = client.post("/auth/login", json={"email": email, "password": "SecurePass123"})
    assert response.status_code == 200
    return user, response.json()["access_token"]


def _create_salon(token: str, name: str = "Test Salon") -> dict:
    """Helper: create salon and return response."""
    response = client.post("/salons", headers={"Authorization": f"Bearer {token}"}, json={"name": name})
    assert response.status_code == 201
    return response.json()


def _add_membership(db: Session, salon_id: str, user_id: uuid.UUID, role: str) -> SalonMembership:
    """Helper: directly add membership to database."""
    membership = SalonMembership(salon_id=salon_id, user_id=user_id, role=role, status="active")
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def test_owner_can_invite_manager(db_session: Session):
    """Test owner can create manager invitation."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner@example.com")
    salon = _create_salon(owner_token, "Manager Invite Salon")

    response = client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "manager@example.com", "role": "manager"},
    )

    assert response.status_code == 201
    data = response.json()
    assert "invitation_id" in data
    assert "token" in data
    assert len(data["token"]) > 30


def test_owner_can_invite_staff(db_session: Session):
    """Test owner can create staff invitation."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner-staff@example.com")
    salon = _create_salon(owner_token, "Staff Invite Salon")

    response = client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "staff@example.com", "role": "staff"},
    )

    assert response.status_code == 201


def test_manager_can_invite_staff(db_session: Session):
    """Test manager can create staff invitation."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner-mgr-invite@example.com")
    salon = _create_salon(owner_token, "Manager Staff Invite Salon")

    manager_user, manager_token = _create_user_and_login(db_session, "manager-invite@example.com")
    _add_membership(db_session, salon["id"], manager_user.id, "manager")

    response = client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"email": "staff-by-mgr@example.com", "role": "staff"},
    )

    assert response.status_code == 201


def test_manager_cannot_invite_manager(db_session: Session):
    """Test manager cannot create manager invitation."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner-mgr-block@example.com")
    salon = _create_salon(owner_token, "Manager Block Salon")

    manager_user, manager_token = _create_user_and_login(db_session, "manager-block@example.com")
    _add_membership(db_session, salon["id"], manager_user.id, "manager")

    response = client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"email": "another-mgr@example.com", "role": "manager"},
    )

    assert response.status_code == 403


def test_staff_cannot_invite(db_session: Session):
    """Test staff cannot create any invitation."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner-staff-block@example.com")
    salon = _create_salon(owner_token, "Staff Block Salon")

    staff_user, staff_token = _create_user_and_login(db_session, "staff-block@example.com")
    _add_membership(db_session, salon["id"], staff_user.id, "staff")

    response = client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"email": "someone@example.com", "role": "staff"},
    )

    assert response.status_code == 403


def test_accept_invitation_creates_membership(db_session: Session):
    """Test accepting invitation creates active membership."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner-accept@example.com")
    salon = _create_salon(owner_token, "Accept Salon")

    invitee_user, invitee_token = _create_user_and_login(db_session, "invitee@example.com")

    # Create invitation
    invite_response = client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "invitee@example.com", "role": "staff"},
    )
    raw_token = invite_response.json()["token"]

    # Accept invitation
    accept_response = client.post(
        "/invitations/accept",
        headers={"Authorization": f"Bearer {invitee_token}"},
        json={"token": raw_token},
    )

    assert accept_response.status_code == 200
    membership_data = accept_response.json()
    assert membership_data["role"] == "staff"
    assert membership_data["status"] == "active"


def test_accept_invitation_email_mismatch(db_session: Session):
    """Test accepting invitation with wrong email fails."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner-mismatch@example.com")
    salon = _create_salon(owner_token, "Mismatch Salon")

    wrong_user, wrong_token = _create_user_and_login(db_session, "wrong@example.com")

    # Create invitation for different email
    invite_response = client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "intended@example.com", "role": "staff"},
    )
    raw_token = invite_response.json()["token"]

    # Try to accept with wrong user
    accept_response = client.post(
        "/invitations/accept",
        headers={"Authorization": f"Bearer {wrong_token}"},
        json={"token": raw_token},
    )

    assert accept_response.status_code == 404


def test_accept_invitation_already_member(db_session: Session):
    """Test accepting invitation when already member fails."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner-duplicate@example.com")
    salon = _create_salon(owner_token, "Duplicate Salon")

    existing_user, existing_token = _create_user_and_login(db_session, "existing@example.com")
    _add_membership(db_session, salon["id"], existing_user.id, "staff")

    # Create invitation for existing member
    invite_response = client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "existing@example.com", "role": "manager"},
    )
    raw_token = invite_response.json()["token"]

    # Try to accept
    accept_response = client.post(
        "/invitations/accept",
        headers={"Authorization": f"Bearer {existing_token}"},
        json={"token": raw_token},
    )

    assert accept_response.status_code == 409


def test_accept_expired_invitation(db_session: Session):
    """Test accepting expired invitation fails."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner-expired@example.com")
    salon = _create_salon(owner_token, "Expired Salon")

    invitee_user, invitee_token = _create_user_and_login(db_session, "expired-invitee@example.com")

    # Create invitation and manually expire it
    invite_response = client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "expired-invitee@example.com", "role": "staff"},
    )
    invitation_id = invite_response.json()["invitation_id"]
    raw_token = invite_response.json()["token"]

    invitation = db_session.get(SalonInvitation, uuid.UUID(invitation_id))
    assert invitation is not None
    invitation.expires_at = datetime.now(UTC) - timedelta(days=1)
    db_session.commit()

    # Try to accept expired invitation
    accept_response = client.post(
        "/invitations/accept",
        headers={"Authorization": f"Bearer {invitee_token}"},
        json={"token": raw_token},
    )

    assert accept_response.status_code == 404


def test_revoke_invitation(db_session: Session):
    """Test owner can revoke pending invitation."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner-revoke@example.com")
    salon = _create_salon(owner_token, "Revoke Salon")

    invite_response = client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "revoked@example.com", "role": "staff"},
    )
    invitation_id = invite_response.json()["invitation_id"]

    revoke_response = client.delete(
        f"/salons/{salon['id']}/invitations/{invitation_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert revoke_response.status_code == 200


def test_accept_revoked_invitation(db_session: Session):
    """Test accepting revoked invitation fails."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner-accept-revoked@example.com")
    salon = _create_salon(owner_token, "Accept Revoked Salon")

    invitee_user, invitee_token = _create_user_and_login(db_session, "revoked-invitee@example.com")

    invite_response = client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "revoked-invitee@example.com", "role": "staff"},
    )
    invitation_id = invite_response.json()["invitation_id"]
    raw_token = invite_response.json()["token"]

    # Revoke invitation
    client.delete(
        f"/salons/{salon['id']}/invitations/{invitation_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    # Try to accept revoked invitation
    accept_response = client.post(
        "/invitations/accept",
        headers={"Authorization": f"Bearer {invitee_token}"},
        json={"token": raw_token},
    )

    assert accept_response.status_code == 404


def test_list_invitations(db_session: Session):
    """Test owner/manager can list salon invitations."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner-list@example.com")
    salon = _create_salon(owner_token, "List Salon")

    # Create multiple invitations
    client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "inv1@example.com", "role": "staff"},
    )
    client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "inv2@example.com", "role": "manager"},
    )

    # List invitations
    list_response = client.get(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert list_response.status_code == 200
    invitations = list_response.json()
    assert len(invitations) == 2


def test_cross_tenant_invitation_revoke_404(db_session: Session):
    """Test revoking invitation from different salon returns 404."""
    owner_a, token_a = _create_user_and_login(db_session, "owner-a-cross@example.com")
    salon_a = _create_salon(token_a, "Salon A Cross")

    owner_b, token_b = _create_user_and_login(db_session, "owner-b-cross@example.com")
    salon_b = _create_salon(token_b, "Salon B Cross")

    # Create invitation in salon B
    invite_response = client.post(
        f"/salons/{salon_b['id']}/invitations",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"email": "cross-inv@example.com", "role": "staff"},
    )
    invitation_id = invite_response.json()["invitation_id"]

    # Try to revoke from salon A
    revoke_response = client.delete(
        f"/salons/{salon_a['id']}/invitations/{invitation_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert revoke_response.status_code == 404
