"""Staff weekly availability business logic with overlap detection."""

from datetime import time
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import SalonMembership, StaffProfile, StaffWeeklyAvailability


def _check_overlap(
    db: Session,
    staff_profile_id: UUID,
    day_of_week: int,
    start_time: time,
    end_time: time,
    exclude_id: UUID | None = None,
) -> StaffWeeklyAvailability | None:
    """Check if a time slot overlaps with existing availability.

    Overlap occurs when:
    new_start < existing_end AND new_end > existing_start

    Args:
        db: Database session
        staff_profile_id: Staff profile UUID
        day_of_week: Day of week (0-6)
        start_time: Slot start time
        end_time: Slot end time
        exclude_id: Optional availability ID to exclude (for PATCH)

    Returns:
        First overlapping availability slot, or None if no overlap
    """
    query = db.query(StaffWeeklyAvailability).filter(
        StaffWeeklyAvailability.staff_profile_id == staff_profile_id,
        StaffWeeklyAvailability.day_of_week == day_of_week,
        StaffWeeklyAvailability.start_time < end_time,
        StaffWeeklyAvailability.end_time > start_time,
    )

    if exclude_id is not None:
        query = query.filter(StaffWeeklyAvailability.id != exclude_id)

    return query.first()


def create_availability(
    db: Session,
    staff_profile_id: UUID,
    day_of_week: int,
    start_time: time,
    end_time: time,
    salon_id: UUID,
) -> StaffWeeklyAvailability:
    """Create a new weekly availability slot.

    Args:
        db: Database session
        staff_profile_id: Staff profile UUID
        day_of_week: Day of week (0-6)
        start_time: Slot start time
        end_time: Slot end time
        salon_id: Current tenant salon UUID (for cross-salon validation)

    Returns:
        Created StaffWeeklyAvailability

    Raises:
        ValueError: If profile not found, wrong salon, or overlap detected
    """
    # Validate profile exists and belongs to salon
    profile = (
        db.query(StaffProfile)
        .join(SalonMembership, StaffProfile.membership_id == SalonMembership.id)
        .filter(
            StaffProfile.id == staff_profile_id,
            SalonMembership.salon_id == salon_id,
        )
        .first()
    )

    if not profile:
        raise ValueError("Staff profile not found")

    # Check for overlap
    overlapping = _check_overlap(db, staff_profile_id, day_of_week, start_time, end_time)
    if overlapping:
        raise ValueError(
            f"Time slot overlaps with existing availability "
            f"({overlapping.start_time.strftime('%H:%M')}-{overlapping.end_time.strftime('%H:%M')})"
        )

    availability = StaffWeeklyAvailability(
        staff_profile_id=staff_profile_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
    )
    db.add(availability)
    db.flush()
    db.refresh(availability)
    return availability


def list_availability(
    db: Session,
    staff_profile_id: UUID,
    salon_id: UUID,
) -> list[StaffWeeklyAvailability]:
    """List all availability slots for a staff profile.

    Args:
        db: Database session
        staff_profile_id: Staff profile UUID
        salon_id: Current tenant salon UUID (for cross-salon validation)

    Returns:
        List of availability slots, ordered by day_of_week and start_time
    """
    # Verify profile belongs to salon
    profile = (
        db.query(StaffProfile)
        .join(SalonMembership, StaffProfile.membership_id == SalonMembership.id)
        .filter(
            StaffProfile.id == staff_profile_id,
            SalonMembership.salon_id == salon_id,
        )
        .first()
    )

    if not profile:
        return []

    return (
        db.query(StaffWeeklyAvailability)
        .filter(StaffWeeklyAvailability.staff_profile_id == staff_profile_id)
        .order_by(StaffWeeklyAvailability.day_of_week, StaffWeeklyAvailability.start_time)
        .all()
    )


def get_availability(
    db: Session,
    availability_id: UUID,
    salon_id: UUID,
) -> StaffWeeklyAvailability | None:
    """Get a single availability slot by ID.

    Args:
        db: Database session
        availability_id: Availability UUID
        salon_id: Current tenant salon UUID (for cross-salon validation)

    Returns:
        Availability slot if found and belongs to salon, None otherwise
    """
    return (
        db.query(StaffWeeklyAvailability)
        .join(StaffProfile, StaffWeeklyAvailability.staff_profile_id == StaffProfile.id)
        .join(SalonMembership, StaffProfile.membership_id == SalonMembership.id)
        .filter(
            StaffWeeklyAvailability.id == availability_id,
            SalonMembership.salon_id == salon_id,
        )
        .first()
    )


def update_availability(
    db: Session,
    availability: StaffWeeklyAvailability,
    **fields,
) -> StaffWeeklyAvailability:
    """Update an availability slot.

    Args:
        db: Database session
        availability: Existing availability slot
        **fields: Fields to update (day_of_week, start_time, end_time)

    Returns:
        Updated availability slot

    Raises:
        ValueError: If update would create overlap or invalid time order
    """
    # Build updated values
    new_day = fields.get("day_of_week", availability.day_of_week)
    new_start = fields.get("start_time", availability.start_time)
    new_end = fields.get("end_time", availability.end_time)

    # Validate time order
    if new_start >= new_end:
        raise ValueError("start_time must be less than end_time")

    # Check overlap (excluding current slot)
    overlapping = _check_overlap(
        db,
        availability.staff_profile_id,
        new_day,
        new_start,
        new_end,
        exclude_id=availability.id,
    )
    if overlapping:
        raise ValueError(
            f"Time slot overlaps with existing availability "
            f"({overlapping.start_time.strftime('%H:%M')}-{overlapping.end_time.strftime('%H:%M')})"
        )

    # Apply updates
    for field_name, value in fields.items():
        if field_name in ("day_of_week", "start_time", "end_time"):
            setattr(availability, field_name, value)

    db.flush()
    db.refresh(availability)
    return availability


def delete_availability(
    db: Session,
    availability: StaffWeeklyAvailability,
) -> None:
    """Delete an availability slot.

    Args:
        db: Database session
        availability: Availability slot to delete
    """
    db.delete(availability)
    db.flush()
