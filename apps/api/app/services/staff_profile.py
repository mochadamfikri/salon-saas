"""Staff profile and staff-service assignment business logic."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import SalonMembership, SalonService, StaffProfile, StaffServiceAssignment


def create_staff_profile(
    db: Session,
    membership_id: UUID,
    salon_id: UUID,
) -> StaffProfile:
    """Create a new staff profile.

    Args:
        db: Database session
        membership_id: Target membership UUID
        salon_id: Current tenant salon UUID (for cross-salon validation)

    Returns:
        Created StaffProfile

    Raises:
        ValueError: If membership not found, wrong salon, suspended, or already has profile
    """
    # Load membership with eager relationship to check salon
    membership = db.query(SalonMembership).filter(SalonMembership.id == membership_id).first()

    if not membership:
        raise ValueError("Membership not found")

    # Cross-salon guard
    if membership.salon_id != salon_id:
        raise ValueError("Membership does not belong to this salon")

    # Active membership guard
    if membership.status != "active":
        raise ValueError("Cannot create profile for suspended membership")

    # Duplicate profile guard
    existing_profile = (
        db.query(StaffProfile).filter(StaffProfile.membership_id == membership_id).first()
    )
    if existing_profile:
        raise ValueError("Membership already has a staff profile")

    profile = StaffProfile(membership_id=membership_id)
    db.add(profile)
    db.flush()
    db.refresh(profile)
    return profile


def list_staff_profiles(db: Session, salon_id: UUID) -> list[StaffProfile]:
    """List all staff profiles in a salon."""
    return (
        db.query(StaffProfile)
        .join(SalonMembership, StaffProfile.membership_id == SalonMembership.id)
        .filter(SalonMembership.salon_id == salon_id)
        .all()
    )


def get_staff_profile(
    db: Session,
    staff_profile_id: UUID,
    salon_id: UUID,
) -> StaffProfile | None:
    """Get a staff profile by ID, scoped to salon."""
    return (
        db.query(StaffProfile)
        .join(SalonMembership, StaffProfile.membership_id == SalonMembership.id)
        .filter(
            StaffProfile.id == staff_profile_id,
            SalonMembership.salon_id == salon_id,
        )
        .first()
    )


def update_staff_profile(
    db: Session,
    profile: StaffProfile,
    **fields,
) -> StaffProfile:
    """Update personal fields of a staff profile.

    All personal fields (display_name, phone, bio, photo_url) are nullable.
    Explicit None clears the field; omitted fields are unchanged.
    """
    allowed_personal_fields = {"display_name", "phone", "bio", "photo_url"}

    for field_name, value in fields.items():
        if field_name in allowed_personal_fields:
            setattr(profile, field_name, value)

    db.flush()
    db.refresh(profile)
    return profile


def toggle_staff_bookable(
    db: Session,
    profile: StaffProfile,
    is_bookable: bool,
) -> StaffProfile:
    """Toggle is_bookable flag (Owner/Manager only)."""
    profile.is_bookable = is_bookable
    db.flush()
    db.refresh(profile)
    return profile


# ============================================================================
# Staff-Service Assignment Operations
# ============================================================================


def create_staff_service_assignment(
    db: Session,
    staff_profile_id: UUID,
    service_id: UUID,
    salon_id: UUID,
) -> StaffServiceAssignment:
    """Create a staff-service assignment.

    Args:
        db: Database session
        staff_profile_id: Staff profile UUID
        service_id: Service UUID
        salon_id: Current tenant salon UUID (for cross-salon validation)

    Returns:
        Created StaffServiceAssignment

    Raises:
        ValueError: If profile/service not found, cross-salon mismatch, or duplicate
    """
    # Load staff profile with membership
    profile = (
        db.query(StaffProfile)
        .join(SalonMembership, StaffProfile.membership_id == SalonMembership.id)
        .filter(StaffProfile.id == staff_profile_id)
        .first()
    )
    if not profile:
        raise ValueError("Staff profile not found")

    # Load service
    service = db.get(SalonService, service_id)
    if not service:
        raise ValueError("Service not found")

    # Cross-salon invariant enforcement
    if profile.membership.salon_id != salon_id:
        raise ValueError("Staff profile does not belong to this salon")
    if service.salon_id != salon_id:
        raise ValueError("Service does not belong to this salon")
    if profile.membership.salon_id != service.salon_id:
        raise ValueError("Staff and service must belong to the same salon")

    # Duplicate assignment guard
    existing = (
        db.query(StaffServiceAssignment)
        .filter(
            StaffServiceAssignment.staff_profile_id == staff_profile_id,
            StaffServiceAssignment.salon_service_id == service_id,
        )
        .first()
    )
    if existing:
        raise ValueError("Assignment already exists")

    assignment = StaffServiceAssignment(
        staff_profile_id=staff_profile_id,
        salon_service_id=service_id,
    )
    db.add(assignment)
    db.flush()
    db.refresh(assignment)
    return assignment


def list_staff_service_assignments(
    db: Session,
    staff_profile_id: UUID,
    salon_id: UUID,
) -> list[StaffServiceAssignment]:
    """List all service assignments for a staff profile."""
    # Verify profile belongs to salon
    profile = get_staff_profile(db, staff_profile_id, salon_id)
    if not profile:
        return []

    return (
        db.query(StaffServiceAssignment)
        .filter(StaffServiceAssignment.staff_profile_id == staff_profile_id)
        .all()
    )


def get_staff_service_assignment(
    db: Session,
    staff_profile_id: UUID,
    service_id: UUID,
    salon_id: UUID,
) -> StaffServiceAssignment | None:
    """Get a specific staff-service assignment."""
    # Verify profile belongs to salon
    profile = get_staff_profile(db, staff_profile_id, salon_id)
    if not profile:
        return None

    return (
        db.query(StaffServiceAssignment)
        .filter(
            StaffServiceAssignment.staff_profile_id == staff_profile_id,
            StaffServiceAssignment.salon_service_id == service_id,
        )
        .first()
    )


def delete_staff_service_assignment(
    db: Session,
    assignment: StaffServiceAssignment,
) -> None:
    """Delete a staff-service assignment."""
    db.delete(assignment)
    db.flush()
