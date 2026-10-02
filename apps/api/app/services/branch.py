"""Branch business logic."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Branch, Salon


def create_branch(
    db: Session,
    salon_id: UUID,
    name: str,
    code: str,
    timezone: str,
    address: str | None = None,
    phone: str | None = None,
) -> Branch:
    """Create a new branch for a salon.

    Args:
        db: Database session
        salon_id: Salon UUID (tenant context)
        name: Branch name
        code: Branch code (unique within salon)
        timezone: IANA timezone identifier
        address: Optional address
        phone: Optional phone

    Returns:
        Created Branch

    Raises:
        ValueError: If salon not found
    """
    salon = db.get(Salon, salon_id)
    if not salon:
        raise ValueError("Salon not found")

    branch = Branch(
        salon_id=salon_id,
        name=name,
        code=code,
        timezone=timezone,
        address=address,
        phone=phone,
        is_active=True,
    )
    db.add(branch)
    db.flush()
    db.refresh(branch)
    return branch


def list_branches(db: Session, salon_id: UUID, active_only: bool = False) -> list[Branch]:
    """List all branches in a salon.

    Args:
        db: Database session
        salon_id: Salon UUID (tenant context)
        active_only: If True, return only active branches

    Returns:
        List of branches, ordered by created_at ascending
    """
    query = db.query(Branch).filter(Branch.salon_id == salon_id)
    if active_only:
        query = query.filter(Branch.is_active == True)  # noqa: E712
    return query.order_by(Branch.created_at.asc()).all()


def get_branch(db: Session, branch_id: UUID, salon_id: UUID) -> Branch | None:
    """Get a branch by ID, scoped to salon.

    Args:
        db: Database session
        branch_id: Branch UUID
        salon_id: Salon UUID (tenant context)

    Returns:
        Branch if found and belongs to salon, None otherwise
    """
    return (
        db.query(Branch)
        .filter(
            Branch.id == branch_id,
            Branch.salon_id == salon_id,
        )
        .first()
    )


def update_branch(
    db: Session,
    branch: Branch,
    **fields,
) -> Branch:
    """Update a branch record.

    Args:
        db: Database session
        branch: Existing branch
        **fields: Fields to update (name, timezone, address, phone)

    Returns:
        Updated branch

    Note:
        code and is_active are immutable through this function.
        Use set_branch_active for activation/deactivation.
    """
    allowed_fields = {"name", "timezone", "address", "phone"}

    for field_name, value in fields.items():
        if field_name in allowed_fields and value is not None:
            setattr(branch, field_name, value)

    db.flush()
    db.refresh(branch)
    return branch


def set_branch_active(db: Session, branch: Branch, is_active: bool) -> Branch:
    """Activate or deactivate a branch.

    Args:
        db: Database session
        branch: Existing branch
        is_active: New activation status

    Returns:
        Updated branch
    """
    branch.is_active = is_active
    db.flush()
    db.refresh(branch)
    return branch
