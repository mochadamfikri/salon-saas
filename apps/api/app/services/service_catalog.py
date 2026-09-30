"""Service catalog business logic."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import SalonService


def create_service(
    db: Session,
    salon_id: UUID,
    name: str,
    duration_minutes: int,
    price_amount: Decimal,
    currency: str = "IDR",
    description: str | None = None,
    category: str | None = None,
) -> SalonService:
    """Create a new salon service."""
    service = SalonService(
        salon_id=salon_id,
        name=name,
        description=description,
        category=category,
        duration_minutes=duration_minutes,
        price_amount=price_amount,
        currency=currency,
    )
    db.add(service)
    db.flush()
    db.refresh(service)
    return service


def list_services(db: Session, salon_id: UUID) -> list[SalonService]:
    """List all services for a salon."""
    return db.query(SalonService).filter(SalonService.salon_id == salon_id).all()


def get_service(db: Session, salon_id: UUID, service_id: UUID) -> SalonService | None:
    """Get a specific service by ID, scoped to salon."""
    return (
        db.query(SalonService)
        .filter(SalonService.id == service_id, SalonService.salon_id == salon_id)
        .first()
    )


def update_service(
    db: Session,
    service: SalonService,
    **fields,
) -> SalonService:
    """Update an existing service.

    Nullable fields (description, category) can be explicitly cleared with None.
    Non-nullable fields (name, duration_minutes, price_amount, currency) reject None.
    Omitted fields are not changed.
    """
    nullable_fields = {"description", "category"}
    required_fields = {"name", "duration_minutes", "price_amount", "currency"}

    for field_name, value in fields.items():
        if value is None and field_name in required_fields:
            raise ValueError(f"Field '{field_name}' cannot be set to null")

        # For nullable fields, None is valid and clears the field
        # For required fields, None already rejected above
        # For all fields, if present in kwargs, update regardless of value
        if field_name in nullable_fields or field_name in required_fields:
            setattr(service, field_name, value)

    db.flush()
    db.refresh(service)
    return service


def activate_service(db: Session, service: SalonService) -> SalonService:
    """Activate a service."""
    service.is_active = True
    db.flush()
    db.refresh(service)
    return service


def deactivate_service(db: Session, service: SalonService) -> SalonService:
    """Deactivate a service."""
    service.is_active = False
    db.flush()
    db.refresh(service)
    return service
