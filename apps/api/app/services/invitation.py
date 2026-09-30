"""Invitation service layer: create, list, revoke, accept."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tokens import generate_opaque_token, hash_token
from app.models import Salon, SalonInvitation, SalonMembership, User


class InvitationError(Exception):
    """Base invitation error."""


class InvitationNotFoundError(InvitationError):
    """Invitation not found, expired, revoked, or already accepted."""


class DuplicateMembershipError(InvitationError):
    """User already has active membership in this salon."""


def create_invitation(
    db: Session, salon: Salon, email: str, role: str, inviter_user_id: uuid.UUID
) -> tuple[SalonInvitation, str]:
    """Create a new salon invitation with hashed token.

    Args:
        db: Database session.
        salon: Salon entity.
        email: Invitee normalized email.
        role: manager or staff.
        inviter_user_id: User creating the invitation.

    Returns:
        Tuple of (SalonInvitation, raw_token).
    """
    settings = get_settings()
    raw_token = generate_opaque_token()

    invitation = SalonInvitation(
        salon_id=salon.id,
        email=email.strip().lower(),
        role=role,
        token_hash=hash_token(raw_token),
        invited_by_user_id=inviter_user_id,
        expires_at=datetime.now(UTC) + timedelta(days=settings.invitation_days),
    )
    db.add(invitation)
    db.flush()

    return invitation, raw_token


def list_salon_invitations(db: Session, salon_id: uuid.UUID) -> list[SalonInvitation]:
    """List all invitations for a salon (active and historical)."""
    stmt = select(SalonInvitation).where(SalonInvitation.salon_id == salon_id)
    return list(db.execute(stmt).scalars().all())


def revoke_invitation(db: Session, invitation_id: uuid.UUID, salon_id: uuid.UUID) -> None:
    """Revoke a pending invitation.

    Args:
        db: Database session.
        invitation_id: Invitation UUID.
        salon_id: Expected salon UUID (cross-tenant protection).

    Raises:
        InvitationNotFoundError: If not found or already accepted/revoked.
    """
    invitation = db.get(SalonInvitation, invitation_id)
    if not invitation or invitation.salon_id != salon_id:
        raise InvitationNotFoundError("Invitation not found")

    if invitation.accepted_at is not None:
        raise InvitationNotFoundError("Invitation already accepted")

    if invitation.revoked_at is not None:
        raise InvitationNotFoundError("Invitation already revoked")

    invitation.revoked_at = datetime.now(UTC)
    db.flush()


def accept_invitation(db: Session, raw_token: str, accepting_user: User) -> SalonMembership:
    """Accept an invitation and create active membership.

    Args:
        db: Database session.
        raw_token: Raw invitation token.
        accepting_user: Authenticated user accepting invitation.

    Returns:
        Created SalonMembership.

    Raises:
        InvitationNotFoundError: Token invalid, expired, revoked, or accepted.
        DuplicateMembershipError: User already has membership in target salon.
    """
    token_hash_value = hash_token(raw_token)
    now = datetime.now(UTC)

    stmt = select(SalonInvitation).where(SalonInvitation.token_hash == token_hash_value)
    invitation = db.execute(stmt).scalar_one_or_none()

    if not invitation:
        raise InvitationNotFoundError("Invalid invitation token")

    if invitation.accepted_at is not None:
        raise InvitationNotFoundError("Invitation already accepted")

    if invitation.revoked_at is not None:
        raise InvitationNotFoundError("Invitation has been revoked")

    if invitation.expires_at < now:
        raise InvitationNotFoundError("Invitation has expired")

    # Verify email matches (normalized)
    if accepting_user.email != invitation.email:
        raise InvitationNotFoundError("Invitation email does not match authenticated user")

    # Check for existing membership
    existing = (
        db.execute(
            select(SalonMembership).where(
                and_(
                    SalonMembership.salon_id == invitation.salon_id,
                    SalonMembership.user_id == accepting_user.id,
                )
            )
        )
        .scalar_one_or_none()
    )

    if existing:
        raise DuplicateMembershipError("User already has membership in this salon")

    # Mark invitation accepted
    invitation.accepted_at = now

    # Create membership
    membership = SalonMembership(
        salon_id=invitation.salon_id,
        user_id=accepting_user.id,
        role=invitation.role,
        status="active",
        joined_at=now,
    )
    db.add(membership)
    db.flush()

    return membership
