"""Salon customer business logic."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Salon, SalonCustomer


def create_customer(
    db: Session,
    salon_id: UUID,
    full_name: str,
    email: str | None = None,
    phone: str | None = None,
    notes: str | None = None,
) -> SalonCustomer:
    """Create a new salon customer.

    Args:
        db: Database session
        salon_id: Salon UUID (tenant context)
        full_name: Customer full name (required, non-empty after trim)
        email: Optional email (normalized, duplicates allowed)
        phone: Optional phone (duplicates allowed)
        notes: Optional notes

    Returns:
        Created SalonCustomer

    Raises:
        ValueError: If salon not found or full_name is blank
    """
    # Verify salon exists
    salon = db.get(Salon, salon_id)
    if not salon:
        raise ValueError("Salon not found")

    customer = SalonCustomer(
        salon_id=salon_id,
        full_name=full_name,
        email=email,
        phone=phone,
        notes=notes,
    )
    db.add(customer)
    db.flush()
    db.refresh(customer)
    return customer


def list_customers(db: Session, salon_id: UUID) -> list[SalonCustomer]:
    """List all customers in a salon.

    Args:
        db: Database session
        salon_id: Salon UUID (tenant context)

    Returns:
        List of customers, ordered by created_at descending
    """
    return (
        db.query(SalonCustomer)
        .filter(SalonCustomer.salon_id == salon_id)
        .order_by(SalonCustomer.created_at.desc())
        .all()
    )


def get_customer(
    db: Session,
    customer_id: UUID,
    salon_id: UUID,
) -> SalonCustomer | None:
    """Get a customer by ID, scoped to salon.

    Args:
        db: Database session
        customer_id: Customer UUID
        salon_id: Salon UUID (tenant context)

    Returns:
        Customer if found and belongs to salon, None otherwise
    """
    return (
        db.query(SalonCustomer)
        .filter(
            SalonCustomer.id == customer_id,
            SalonCustomer.salon_id == salon_id,
        )
        .first()
    )


def update_customer(
    db: Session,
    customer: SalonCustomer,
    **fields,
) -> SalonCustomer:
    """Update a customer record.

    Args:
        db: Database session
        customer: Existing customer
        **fields: Fields to update (full_name, email, phone, notes)

    Returns:
        Updated customer

    Raises:
        ValueError: If full_name would become blank
    """
    allowed_fields = {"full_name", "email", "phone", "notes"}

    for field_name, value in fields.items():
        if field_name in allowed_fields:
            setattr(customer, field_name, value)

    db.flush()
    db.refresh(customer)
    return customer
