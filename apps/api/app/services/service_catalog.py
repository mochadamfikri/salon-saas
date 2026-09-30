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
    name: str | None = None,
    description: str | None = None,
    category: str | None = None,
    duration_minutes: int | None = None,
    price_amount: Decimal | None = None,
    currency: str | None = None,
) -> SalonService:
    """Update an existing service."""
    if name is not None:
        service.name = name
    if description is not None:
        service.description = description
    if category is not None:
        service.category = category
    if duration_minutes is not None:
        service.duration_minutes = duration_minutes
    if price_amount is not None:
        service.price_amount = price_amount
    if currency is not None:
        service.currency = currency
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
