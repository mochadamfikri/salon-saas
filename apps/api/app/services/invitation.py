"""Invitation service layer: create, list, revoke, accept."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tokens import generate_opaque_token, hash_token
from app.models import Salon, SalonInvitation, SalonMembership, User


class InvitationError(Exception):
    """Base invitation error."""


class InvitationNotFoundError(InvitationError):
    """Token is invalid or unknown."""


class InvitationExpiredError(InvitationError):
    """Invitation is past its expiry time."""


class InvitationRevokedError(InvitationError):
    """Invitation was revoked before acceptance."""


class InvitationAlreadyAcceptedError(InvitationError):
    """Invitation was already redeemed."""


class InvitationEmailMismatchError(InvitationError):
    """Authenticated user email does not match the invited email."""


class DuplicateMembershipError(InvitationError):
    """User already has a membership in this salon."""


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


def accept_invitation(
    db: Session, raw_token: str, accepting_user: User
) -> tuple[SalonMembership, Salon]:
    """Accept an invitation and create an active membership.

    Concurrency-safe: the invitation row is locked (SELECT ... FOR UPDATE) so
    concurrent redemptions of the same token serialize — exactly one wins and
    the loser observes ``accepted_at``. The ``uq_salon_memberships_salon_user``
    unique constraint is the backstop for races across distinct invitations
    (same user + salon); a lost race surfaces as ``DuplicateMembershipError``.

    The returned salon is loaded server-side from the invitation itself; the
    client never supplies a salon_id to this endpoint.

    Args:
        db: Database session.
        raw_token: Raw invitation token (hashed before comparison; never logged).
        accepting_user: Authenticated user accepting the invitation.

    Returns:
        Tuple of (created SalonMembership, invitation's Salon).

    Raises:
        InvitationNotFoundError: Token invalid or unknown.
        InvitationAlreadyAcceptedError: Invitation already redeemed.
        InvitationRevokedError: Invitation was revoked.
        InvitationExpiredError: Invitation is past its expiry.
        InvitationEmailMismatchError: Authenticated email != invited email.
        DuplicateMembershipError: User already has a membership in this salon.
    """
    token_hash_value = hash_token(raw_token)
    now = datetime.now(UTC)

    # Row-level lock: concurrent redemptions of the same invitation serialize
    # here; the loser observes accepted_at and is rejected. Never two winners.
    stmt = (
        select(SalonInvitation)
        .where(SalonInvitation.token_hash == token_hash_value)
        .with_for_update()
    )
    invitation = db.execute(stmt).scalar_one_or_none()

    if invitation is None:
        raise InvitationNotFoundError("Invalid invitation token")

    if invitation.accepted_at is not None:
        raise InvitationAlreadyAcceptedError("Invitation has already been accepted")

    if invitation.revoked_at is not None:
        raise InvitationRevokedError("Invitation has been revoked")

    if invitation.expires_at < now:
        raise InvitationExpiredError("Invitation has expired")

    # Normalized email comparison (both sides are normalized on write, but
    # normalize again defensively — never trust caller-controlled values).
    if accepting_user.email.strip().lower() != invitation.email.strip().lower():
        raise InvitationEmailMismatchError(
            "Invitation email mismatch: this invitation was sent to a different email address"
        )

    # Pre-check for a friendlier error; the unique constraint below is the
    # authoritative guard under concurrency. A duplicate rejection does NOT
    # consume the invitation (accepted_at is only set on success).
    existing = db.execute(
        select(SalonMembership).where(
            and_(
                SalonMembership.salon_id == invitation.salon_id,
                SalonMembership.user_id == accepting_user.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise DuplicateMembershipError("User already has an active membership in this salon")

    # Mark invitation accepted (one-time semantics).
    invitation.accepted_at = now

    membership = SalonMembership(
        salon_id=invitation.salon_id,
        user_id=accepting_user.id,
        role=invitation.role,
        status="active",
        joined_at=now,
    )
    db.add(membership)
    try:
        db.flush()
    except IntegrityError as e:
        # Lost a concurrent race (e.g. two distinct invitations for the same
        # user+salon redeemed at once). Roll back and re-check authoritatively:
        # if the membership now exists, the other transaction won.
        db.rollback()
        winner = db.execute(
            select(SalonMembership).where(
                and_(
                    SalonMembership.salon_id == invitation.salon_id,
                    SalonMembership.user_id == accepting_user.id,
                )
            )
        ).scalar_one_or_none()
        if winner is not None:
            raise DuplicateMembershipError(
                "User already has an active membership in this salon"
            ) from e
        raise

    # Salon context is loaded server-side from the invitation; the client
    # never supplies a salon_id to this endpoint.
    salon = db.get(Salon, invitation.salon_id)
    if salon is None:  # pragma: no cover - FK RESTRICT guarantees presence
        raise InvitationNotFoundError("Invalid invitation token")

    return membership, salon
