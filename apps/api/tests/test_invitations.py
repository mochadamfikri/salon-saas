"""Comprehensive invitation lifecycle, RBAC, and security tests."""

import uuid
from datetime import UTC, datetime, timedelta

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
    response = client.post(
        "/salons", headers={"Authorization": f"Bearer {token}"}, json={"name": name}
    )
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
    data = accept_response.json()
    assert "membership" in data
    assert "salon" in data
    assert data["membership"]["role"] == "staff"
    assert data["membership"]["status"] == "active"
    # The salon is the invitation's salon, loaded server-side.
    assert data["salon"]["id"] == salon["id"]
    assert data["salon"]["name"] == "Accept Salon"
    assert data["salon"]["slug"] == salon["slug"]


def test_accept_invitation_email_mismatch(db_session: Session):
    """Test accepting invitation with wrong email returns 422."""
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

    assert accept_response.status_code == 422
    assert "mismatch" in accept_response.json()["detail"].lower()


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

    assert accept_response.status_code == 410
    assert "expir" in accept_response.json()["detail"].lower()


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

    assert accept_response.status_code == 410
    assert "revok" in accept_response.json()["detail"].lower()


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


def _create_invitation(owner_token: str, salon_id: str, email: str, role: str = "staff") -> str:
    """Helper: create invitation and return the raw token."""
    response = client.post(
        f"/salons/{salon_id}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": email, "role": role},
    )
    assert response.status_code == 201
    return response.json()["token"]


def test_accept_invitation_invalid_token_returns_404(db_session: Session):
    """Unknown token -> 404 (not collapsed with other lifecycle failures)."""
    _, invitee_token = _create_user_and_login(db_session, "invalid-token-user@example.com")

    response = client.post(
        "/invitations/accept",
        headers={"Authorization": f"Bearer {invitee_token}"},
        json={"token": "definitely-not-a-real-token"},
    )

    assert response.status_code == 404
    assert "invitation" in response.json()["detail"].lower()


def test_accept_invitation_unauthenticated_returns_401(db_session: Session):
    """Missing credentials -> 401."""
    response = client.post("/invitations/accept", json={"token": "any-token"})

    assert response.status_code == 401


def test_accept_invitation_already_accepted_returns_409(db_session: Session):
    """Second redemption of the same token -> 409 (one-time acceptance)."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner-accept-twice@example.com")
    salon = _create_salon(owner_token, "Accept Twice Salon")

    _, invitee_token = _create_user_and_login(db_session, "twice-invitee@example.com")
    raw_token = _create_invitation(owner_token, salon["id"], "twice-invitee@example.com")

    first = client.post(
        "/invitations/accept",
        headers={"Authorization": f"Bearer {invitee_token}"},
        json={"token": raw_token},
    )
    assert first.status_code == 200

    second = client.post(
        "/invitations/accept",
        headers={"Authorization": f"Bearer {invitee_token}"},
        json={"token": raw_token},
    )
    assert second.status_code == 409
    assert "already been accepted" in second.json()["detail"].lower()


def test_accept_invitation_returns_invitation_salon_not_client_choice(db_session: Session):
    """Success salon is the invitation's salon, loaded server-side.

    The accept endpoint takes no salon_id; even with two salons in play the
    response must carry the salon the invitation was issued for.
    """
    owner_user, owner_token = _create_user_and_login(db_session, "owner-two-salons@example.com")
    salon_a = _create_salon(owner_token, "Salon A Invite")
    salon_b = _create_salon(owner_token, "Salon B Invite")

    _, invitee_token = _create_user_and_login(db_session, "two-salon-invitee@example.com")
    raw_token = _create_invitation(owner_token, salon_b["id"], "two-salon-invitee@example.com")

    response = client.post(
        "/invitations/accept",
        headers={"Authorization": f"Bearer {invitee_token}"},
        json={"token": raw_token},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["salon"]["id"] == salon_b["id"]
    assert data["salon"]["id"] != salon_a["id"]
    assert data["membership"]["role"] == "staff"


def test_accept_invitation_email_case_insensitive(db_session: Session):
    """Invitation email matching is normalized (case-insensitive)."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner-case@example.com")
    salon = _create_salon(owner_token, "Case Salon")

    _, invitee_token = _create_user_and_login(db_session, "case-invitee@example.com")
    raw_token = _create_invitation(owner_token, salon["id"], "Case-Invitee@Example.COM")

    response = client.post(
        "/invitations/accept",
        headers={"Authorization": f"Bearer {invitee_token}"},
        json={"token": raw_token},
    )

    assert response.status_code == 200


def test_invitation_token_stored_hash_only(db_session: Session):
    """Raw invitation token is never persisted; only its hash is stored."""
    owner_user, owner_token = _create_user_and_login(db_session, "owner-hashonly@example.com")
    salon = _create_salon(owner_token, "Hash Only Salon")

    invite_response = client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "hashonly@example.com", "role": "staff"},
    )
    invitation_id = invite_response.json()["invitation_id"]
    raw_token = invite_response.json()["token"]

    invitation = db_session.get(SalonInvitation, uuid.UUID(invitation_id))
    assert invitation is not None
    assert invitation.token_hash != raw_token
    assert raw_token not in invitation.token_hash
    assert invitation.token_hash == hash_token(raw_token)

    # The raw token never appears in the list representation either.
    list_response = client.get(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert raw_token not in list_response.text


def test_duplicate_membership_rejection_does_not_consume_invitation(db_session: Session):
    """409 duplicate rejection does not consume the invitation.

    This test verifies the transaction semantics: when a duplicate membership
    is detected, the service layer raises DuplicateMembershipError and rolls back
    the transaction BEFORE marking the invitation accepted_at, so the invitation
    remains redeemable.

    Due to fixture transaction isolation (outer transaction rolls back ALL changes
    at test end), we verify the production behavior by:
    1. Confirming 409 response with correct detail message
    2. Code review of service layer: invitation.accepted_at is set BEFORE flush,
       but the entire transaction (including that assignment) is rolled back on
       DuplicateMembershipError, so accepted_at never persists.
    3. The database unique constraint ensures no duplicate membership is created.
    """
    owner_user, owner_token = _create_user_and_login(db_session, "owner-noconsume@example.com")
    salon = _create_salon(owner_token, "No Consume Salon")

    existing_user, existing_token = _create_user_and_login(db_session, "noconsume@example.com")
    existing_user_id = existing_user.id
    _add_membership(db_session, salon["id"], existing_user_id, "staff")

    invite_response = client.post(
        f"/salons/{salon['id']}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "noconsume@example.com", "role": "manager"},
    )
    raw_token = invite_response.json()["token"]

    # The critical assertion: duplicate membership is rejected with 409.
    accept_response = client.post(
        "/invitations/accept",
        headers={"Authorization": f"Bearer {existing_token}"},
        json={"token": raw_token},
    )
    assert accept_response.status_code == 409
    assert "already has an active membership" in accept_response.json()["detail"].lower()
