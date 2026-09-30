"""Tenant-scoped Service Catalog API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.tenant import TenantContext, get_tenant_context
from app.models import SalonService
from app.schemas.service import (
    SalonServiceCreateRequest,
    SalonServiceResponse,
    SalonServiceUpdateRequest,
)
from app.services.service_catalog import (
    activate_service,
    create_service,
    deactivate_service,
    get_service,
    list_services,
    update_service,
)

router = APIRouter(tags=["service-catalog"])


def _require_service_mutation_permission(tenant: TenantContext) -> None:
    """Require the owner or manager role for service catalog mutation."""
    tenant.require_owner_or_manager()


def _get_tenant_service_or_404(tenant: TenantContext, service_id: UUID) -> SalonService:
    """Load one service only when it belongs to the current tenant."""
    service = get_service(tenant.db, tenant.salon.id, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


@router.post(
    "/salons/{salon_id}/services",
    response_model=SalonServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service_endpoint(
    payload: SalonServiceCreateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> SalonServiceResponse:
    """Create a service in the path-authoritative salon."""
    _require_service_mutation_permission(tenant)
    service = create_service(
        tenant.db,
        salon_id=tenant.salon.id,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        duration_minutes=payload.duration_minutes,
        price_amount=payload.price_amount,
        currency=payload.currency,
    )
    tenant.db.commit()
    return SalonServiceResponse.model_validate(service)


@router.get("/salons/{salon_id}/services", response_model=list[SalonServiceResponse])
def list_services_endpoint(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> list[SalonServiceResponse]:
    """List active and inactive services for the current tenant."""
    services = list_services(tenant.db, tenant.salon.id)
    return [SalonServiceResponse.model_validate(service) for service in services]


@router.get("/salons/{salon_id}/services/{service_id}", response_model=SalonServiceResponse)
def get_service_endpoint(
    service_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> SalonServiceResponse:
    """Get a service belonging to the current tenant."""
    return SalonServiceResponse.model_validate(_get_tenant_service_or_404(tenant, service_id))


@router.patch("/salons/{salon_id}/services/{service_id}", response_model=SalonServiceResponse)
def update_service_endpoint(
    service_id: UUID,
    payload: SalonServiceUpdateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> SalonServiceResponse:
    """Update a service belonging to the current tenant."""
    _require_service_mutation_permission(tenant)
    service = _get_tenant_service_or_404(tenant, service_id)
    try:
        updated = update_service(tenant.db, service, **payload.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from None
    tenant.db.commit()
    return SalonServiceResponse.model_validate(updated)


@router.post(
    "/salons/{salon_id}/services/{service_id}/activate", response_model=SalonServiceResponse
)
def activate_service_endpoint(
    service_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> SalonServiceResponse:
    """Activate a service belonging to the current tenant."""
    _require_service_mutation_permission(tenant)
    service = activate_service(tenant.db, _get_tenant_service_or_404(tenant, service_id))
    tenant.db.commit()
    return SalonServiceResponse.model_validate(service)


@router.post(
    "/salons/{salon_id}/services/{service_id}/deactivate", response_model=SalonServiceResponse
)
def deactivate_service_endpoint(
    service_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> SalonServiceResponse:
    """Deactivate a service belonging to the current tenant."""
    _require_service_mutation_permission(tenant)
    service = deactivate_service(tenant.db, _get_tenant_service_or_404(tenant, service_id))
    tenant.db.commit()
    return SalonServiceResponse.model_validate(service)
