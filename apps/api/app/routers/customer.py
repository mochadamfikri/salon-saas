"""Tenant-scoped Salon Customer API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.tenant import TenantContext, get_tenant_context
from app.models import SalonCustomer
from app.schemas.customer import CustomerCreateRequest, CustomerResponse, CustomerUpdateRequest
from app.services.customer import create_customer, get_customer, list_customers, update_customer

router = APIRouter(tags=["customers"])


def _get_tenant_customer_or_404(tenant: TenantContext, customer_id: UUID) -> SalonCustomer:
    """Load one customer only when it belongs to the current tenant."""
    customer = get_customer(tenant.db, customer_id, tenant.salon.id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@router.post(
    "/salons/{salon_id}/customers",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_customer_endpoint(
    payload: CustomerCreateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> CustomerResponse:
    """Create a customer in the path-authoritative salon for operational use."""
    customer = create_customer(
        tenant.db,
        salon_id=tenant.salon.id,
        **payload.model_dump(),
    )
    tenant.db.commit()
    return CustomerResponse.model_validate(customer)


@router.get("/salons/{salon_id}/customers", response_model=list[CustomerResponse])
def list_customers_endpoint(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> list[CustomerResponse]:
    """List customers belonging only to the current tenant."""
    return [
        CustomerResponse.model_validate(customer)
        for customer in list_customers(tenant.db, tenant.salon.id)
    ]


@router.get("/salons/{salon_id}/customers/{customer_id}", response_model=CustomerResponse)
def get_customer_endpoint(
    customer_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> CustomerResponse:
    """Get a customer belonging to the current tenant."""
    return CustomerResponse.model_validate(_get_tenant_customer_or_404(tenant, customer_id))


@router.patch("/salons/{salon_id}/customers/{customer_id}", response_model=CustomerResponse)
def update_customer_endpoint(
    customer_id: UUID,
    payload: CustomerUpdateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> CustomerResponse:
    """Update mutable customer fields without allowing tenant ownership changes."""
    customer = _get_tenant_customer_or_404(tenant, customer_id)
    updated = update_customer(tenant.db, customer, **payload.model_dump(exclude_unset=True))
    tenant.db.commit()
    return CustomerResponse.model_validate(updated)
