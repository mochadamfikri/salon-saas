"""Tenant service layer: salon creation, member management, RBAC."""

import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Salon, SalonMembership, User
from app.schemas.tenant import RESERVED_SALON_SLUGS


def generate_unique_salon_slug(db: Session, name: str) -> str:
    """Generate a deterministic, URL-safe, globally unique salon slug.

    The base derives from the salon name; collisions receive `-2`, `-3`, etc.
    Database uniqueness remains the final authority for concurrent requests.
    """
    normalized = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    base = normalized or "salon"
    if base in RESERVED_SALON_SLUGS:
        base = f"{base}-salon"
    base = base[:70].rstrip("-") or "salon"

    candidate = base
    suffix = 2
    while db.scalar(select(Salon.id).where(Salon.slug == candidate)) is not None:
        suffix_text = f"-{suffix}"
        candidate = f"{base[:80 - len(suffix_text)].rstrip('-')}{suffix_text}"
        suffix += 1
    return candidate


def create_salon_with_owner(
    db: Session, name: str, slug: str | None, creator_user: User
) -> tuple[Salon, SalonMembership]:
    """Create salon and assign creator as OWNER atomically."""
    resolved_slug = slug or generate_unique_salon_slug(db, name)
    salon = Salon(
        name=name,
        slug=resolved_slug,
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
    """Update a non-owner member's role after endpoint RBAC authorization."""
    membership = db.get(SalonMembership, membership_id)
    if not membership:
        raise ValueError("Membership not found")
    if membership.role == "owner":
        raise ValueError("Cannot change owner role")
    membership.role = new_role
    db.flush()
    return membership


def remove_member(db: Session, membership_id: uuid.UUID) -> None:
    """Remove a non-owner member after endpoint RBAC authorization."""
    membership = db.get(SalonMembership, membership_id)
    if not membership:
        raise ValueError("Membership not found")
    if membership.role == "owner":
        raise ValueError("Cannot remove owner")
    db.delete(membership)
    db.flush()
