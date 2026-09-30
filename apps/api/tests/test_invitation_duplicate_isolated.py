"""Isolated DB test for duplicate membership invitation invariants.

This test uses real database sessions and commits (outside the fixture transaction
isolation) to verify all 4 invariants when duplicate membership is rejected:
1. Response 409
2. Membership count remains 1 (no duplicate created)
3. Invitation still exists
4. Invitation accepted_at IS NULL (not consumed)
"""

import uuid

from app.core.security import hash_password
from app.db import engine
from app.models import Salon, SalonInvitation, SalonMembership, User
from app.services.invitation import (
    DuplicateMembershipError,
    accept_invitation,
    create_invitation,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_duplicate_membership_rejection_does_not_consume_invitation_isolated():
    """409 duplicate rejection: response 409, membership=1, invitation exists, accepted_at NULL.

    This test manages its own DB session with real commits to verify all invariants
    that fixture-based tests cannot prove due to transaction rollback.
    """
    db = Session(engine)

    # Initialize for cleanup scope
    salon_id = None
    owner_id = None
    existing_user_id = None
    invitation_id = None

    # Setup: owner, salon, user with existing membership, invitation
    try:
        owner = User(
            email=_unique("owner-dup") + "@example.com",
            password_hash=hash_password("SecurePass123"),
            is_active=True,
        )
        existing_user = User(
            email=_unique("existing-dup") + "@example.com",
            password_hash=hash_password("SecurePass123"),
            is_active=True,
        )
        db.add_all([owner, existing_user])
        db.flush()

        salon = Salon(
            name="Duplicate Test Salon",
            slug=_unique("dup-salon"),
            created_by_user_id=owner.id,
        )
        db.add(salon)
        db.flush()

        # Create existing membership (staff role)
        existing_membership = SalonMembership(
            salon_id=salon.id,
            user_id=existing_user.id,
            role="staff",
            status="active",
        )
        db.add(existing_membership)
        db.flush()

        # Create invitation for same user (manager role)
        invitation, raw_token = create_invitation(
            db, salon, existing_user.email, "manager", owner.id
        )
        db.commit()

        # Capture IDs for cleanup and verification
        salon_id = salon.id
        owner_id = owner.id
        existing_user_id = existing_user.id
        invitation_id = invitation.id

        # Attempt to accept invitation (should raise DuplicateMembershipError)
        db_accept = Session(engine)
        try:
            invitee = db_accept.get(User, existing_user_id)
            assert invitee is not None

            try:
                accept_invitation(db_accept, raw_token, invitee)
                db_accept.commit()
                raise AssertionError("Expected DuplicateMembershipError but accept succeeded")
            except DuplicateMembershipError:
                # Expected: duplicate membership detected, transaction rolled back
                db_accept.rollback()
        finally:
            db_accept.close()

        # INVARIANT 1: Response would be 409 (verified by catching DuplicateMembershipError)
        # ✅ DuplicateMembershipError raised

        # INVARIANT 2: Membership count remains 1 (no duplicate created)
        db_verify = Session(engine)
        try:
            membership_count = int(
                db_verify.execute(
                    select(func.count())
                    .select_from(SalonMembership)
                    .where(
                        SalonMembership.salon_id == salon_id,
                        SalonMembership.user_id == existing_user_id,
                    )
                ).scalar()
                or 0
            )
            assert membership_count == 1, f"Expected 1 membership, found {membership_count}"

            # INVARIANT 3: Invitation still exists
            invitation_check = db_verify.get(SalonInvitation, invitation_id)
            assert invitation_check is not None, "Invitation should still exist after 409"

            # INVARIANT 4: Invitation accepted_at IS NULL (not consumed)
            assert invitation_check.accepted_at is None, (
                f"Invitation should NOT be consumed after 409, "
                f"but accepted_at={invitation_check.accepted_at}"
            )
        finally:
            db_verify.close()

    finally:
        # Cleanup: delete all created rows (skip if setup failed early)
        if salon_id is not None:
            db_cleanup = Session(engine)
            try:
                db_cleanup.query(SalonMembership).filter(
                    SalonMembership.salon_id == salon_id
                ).delete(synchronize_session=False)
                db_cleanup.query(SalonInvitation).filter(
                    SalonInvitation.salon_id == salon_id
                ).delete(synchronize_session=False)
                db_cleanup.query(Salon).filter(Salon.id == salon_id).delete(
                    synchronize_session=False
                )
                db_cleanup.query(User).filter(User.id.in_([owner_id, existing_user_id])).delete(
                    synchronize_session=False
                )
                db_cleanup.commit()
            finally:
                db_cleanup.close()
