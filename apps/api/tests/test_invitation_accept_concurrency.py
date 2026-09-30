"""Concurrent invitation acceptance: exactly one winner, never duplicates.

These tests exercise real database-level concurrency (threads with independent
sessions and commits) against the invitation row lock (SELECT ... FOR UPDATE)
and the ``uq_salon_memberships_salon_user`` unique constraint backstop.

They manage their own sessions and commits outside the ``db_session`` fixture
(the fixture's rolled-back transaction would be invisible to other
connections), and they clean up every row they create in a ``finally`` block.
"""

import threading
import uuid

from app.core.security import hash_password
from app.db import engine
from app.models import Salon, SalonInvitation, SalonMembership, User
from app.services.invitation import (
    DuplicateMembershipError,
    InvitationAlreadyAcceptedError,
    accept_invitation,
    create_invitation,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

_REJECTED = (InvitationAlreadyAcceptedError, DuplicateMembershipError)


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _setup_world(num_invitations: int = 1) -> dict:
    """Create owner, salon, invitee, and invitation(s); commit; return ids/tokens."""
    db = Session(engine)
    try:
        owner = User(
            email=_unique("owner") + "@example.com",
            password_hash=hash_password("SecurePass123"),
            is_active=True,
        )
        invitee = User(
            email=_unique("invitee") + "@example.com",
            password_hash=hash_password("SecurePass123"),
            is_active=True,
        )
        db.add_all([owner, invitee])
        db.flush()

        salon = Salon(
            name="Concurrency Salon",
            slug=_unique("concurrency-salon"),
            created_by_user_id=owner.id,
        )
        db.add(salon)
        db.flush()

        raw_tokens = []
        for _ in range(num_invitations):
            _, raw_token = create_invitation(db, salon, invitee.email, "staff", owner.id)
            raw_tokens.append(raw_token)

        db.commit()
        return {
            "salon_id": salon.id,
            "owner_id": owner.id,
            "invitee_id": invitee.id,
            "invitee_email": invitee.email,
            "raw_tokens": raw_tokens,
        }
    finally:
        db.close()


def _teardown_world(world: dict) -> None:
    """Delete every row created by _setup_world (best effort, then commit)."""
    db = Session(engine)
    try:
        salon_id = world["salon_id"]
        db.query(SalonMembership).filter(SalonMembership.salon_id == salon_id).delete(
            synchronize_session=False
        )
        db.query(SalonInvitation).filter(SalonInvitation.salon_id == salon_id).delete(
            synchronize_session=False
        )
        db.query(Salon).filter(Salon.id == salon_id).delete(synchronize_session=False)
        for user_id in (world["owner_id"], world["invitee_id"]):
            db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _membership_count(salon_id: uuid.UUID, user_id: uuid.UUID) -> int:
    db = Session(engine)
    try:
        return int(
            db.execute(
                select(func.count())
                .select_from(SalonMembership)
                .where(
                    SalonMembership.salon_id == salon_id,
                    SalonMembership.user_id == user_id,
                )
            ).scalar()
        )
    finally:
        db.close()


def _run_concurrent_accepts(world: dict, tokens: list[str]) -> list[str]:
    """Race N threads accepting the given tokens; return per-thread outcomes."""
    barrier = threading.Barrier(len(tokens))
    outcomes: list[str] = []

    def attempt(raw_token: str) -> None:
        db = Session(engine)
        try:
            invitee = db.get(User, world["invitee_id"])
            assert invitee is not None
            barrier.wait(timeout=15)
            accept_invitation(db, raw_token, invitee)
            db.commit()
            outcomes.append("accepted")
        except _REJECTED:
            db.rollback()
            outcomes.append("rejected")
        except Exception as exc:  # noqa: BLE001 - surfaced via assertion below
            db.rollback()
            outcomes.append(f"error: {exc!r}")
        finally:
            db.close()

    threads = [threading.Thread(target=attempt, args=(token,)) for token in tokens]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(t.is_alive() for t in threads), "accept threads did not finish"
    return outcomes


def test_concurrent_accept_same_invitation_single_winner():
    """Two threads redeeming the same token: exactly one 200, one 409."""
    world = _setup_world(num_invitations=1)
    try:
        token = world["raw_tokens"][0]
        outcomes = _run_concurrent_accepts(world, [token, token])

        assert sorted(outcomes) == ["accepted", "rejected"], outcomes
        assert _membership_count(world["salon_id"], world["invitee_id"]) == 1

        # The token is consumed exactly once.
        db = Session(engine)
        try:
            used = [
                inv.accepted_at
                for inv in db.query(SalonInvitation)
                .filter(SalonInvitation.salon_id == world["salon_id"])
                .all()
            ]
            assert all(ts is not None for ts in used)
        finally:
            db.close()
    finally:
        _teardown_world(world)


def test_concurrent_accept_distinct_invitations_no_duplicate_membership():
    """Two threads redeeming distinct invitations for the same user+salon.

    The unique constraint backstop must turn the loser into a 409 instead of
    creating a duplicate membership: exactly one membership row survives.
    """
    world = _setup_world(num_invitations=2)
    try:
        outcomes = _run_concurrent_accepts(world, world["raw_tokens"])

        assert sorted(outcomes) == ["accepted", "rejected"], outcomes
        assert _membership_count(world["salon_id"], world["invitee_id"]) == 1
    finally:
        _teardown_world(world)


def test_sequential_double_accept_second_is_409():
    """Sanity: without concurrency, the second accept is already 409."""
    world = _setup_world(num_invitations=1)
    try:
        token = world["raw_tokens"][0]
        db = Session(engine)
        try:
            invitee = db.get(User, world["invitee_id"])
            assert invitee is not None
            membership, salon = accept_invitation(db, token, invitee)
            db.commit()
            assert salon.id == world["salon_id"]
            assert membership.salon_id == world["salon_id"]

            try:
                accept_invitation(db, token, invitee)
                db.commit()
                raise AssertionError("second accept should have raised")
            except InvitationAlreadyAcceptedError:
                db.rollback()
        finally:
            db.close()

        assert _membership_count(world["salon_id"], world["invitee_id"]) == 1
    finally:
        _teardown_world(world)
