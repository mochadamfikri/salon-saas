"""Tenant service layer: salon creation, member management, RBAC."""

import uuid

from sqlalchemy.orm import Session

from app.models import Salon, SalonMembership, User


def create_salon_with_owner(
    db: Session, name: str, slug: str, creator_user: User
) -> tuple[Salon, SalonMembership]:
    """Create a salon and assign creator as OWNER in a single transaction.

    Args:
        db: Database session.
        name: Salon display name.
        slug: Globally unique URL-safe slug.
        creator_user: Authenticated user who becomes the OWNER.

    Returns:
        Tuple of (created_salon, owner_membership).

    Raises:
        IntegrityError: If slug already exists.
    """
    salon = Salon(
        name=name,
        slug=slug,
        status="onboarding",
        created_by_user_id=creator_user.id,
    )
    db.add(salon)
    db.flush()

    membership = SalonMembership(
        salon_id=salon.id,
        user_id=creator_user.id,
        role="owner",
        status="active",
    )
    db.add(membership)
    db.flush()

    return salon, membership


def get_user_salons(db: Session, user_id: uuid.UUID) -> list[SalonMembership]:
    """Return all active salon memberships for a user with joined salon data."""
    return (
        db.query(SalonMembership)
        .filter(SalonMembership.user_id == user_id, SalonMembership.status == "active")
        .all()
    )


def get_salon_members(db: Session, salon_id: uuid.UUID) -> list[SalonMembership]:
    """Return all salon members with user data."""
    return db.query(SalonMembership).filter(SalonMembership.salon_id == salon_id).all()


def update_member_role(db: Session, membership_id: uuid.UUID, new_role: str) -> SalonMembership:
    """Update a non-owner member's role.

    Args:
        db: Database session.
        membership_id: Membership UUID.
        new_role: New role (manager or staff).

    Returns:
        Updated membership.

    Raises:
        ValueError: If trying to change owner role.
    """
    membership = db.get(SalonMembership, membership_id)
    if not membership:
        raise ValueError("Membership not found")

    if membership.role == "owner":
        raise ValueError("Cannot change owner role")

    membership.role = new_role
    db.flush()
    return membership


def remove_member(db: Session, membership_id: uuid.UUID) -> None:
    """Remove a non-owner member from salon.

    Args:
        db: Database session.
        membership_id: Membership UUID.

    Raises:
        ValueError: If trying to remove owner.
    """
    membership = db.get(SalonMembership, membership_id)
    if not membership:
        raise ValueError("Membership not found")

    if membership.role == "owner":
        raise ValueError("Cannot remove owner")

    db.delete(membership)
    db.flush()
