"""Branch management API endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.core.rbac import Permission
from app.core.tenant import TenantContext, get_tenant_context
from app.models import Branch
from app.schemas.branch import (
    BranchActivateRequest,
    BranchCreateRequest,
    BranchResponse,
    BranchUpdateRequest,
)
from app.services.branch import (
    create_branch,
    get_branch,
    list_branches,
    set_branch_active,
    update_branch,
)

router = APIRouter(tags=["branches"])


def _is_expected_duplicate_error(error: IntegrityError, constraint_name: str) -> bool:
    """Return whether an IntegrityError is the expected named UNIQUE constraint."""
    diagnostics = getattr(getattr(error, "orig", None), "diag", None)
    return getattr(diagnostics, "constraint_name", None) == constraint_name


def _get_tenant_branch_or_404(tenant: TenantContext, branch_id: UUID) -> Branch:
    """Load one branch only when it belongs to the current tenant."""
    branch = get_branch(tenant.db, branch_id, tenant.salon.id)
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return branch


@router.post(
    "/salons/{salon_id}/branches",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_branch_endpoint(
    payload: BranchCreateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> BranchResponse:
    """Create a new branch (Owner/Manager only)."""
    tenant.require_permission(Permission.MANAGE_STAFF)
    try:
        branch = create_branch(
            tenant.db,
            salon_id=tenant.salon.id,
            **payload.model_dump(),
        )
        tenant.db.commit()
        return BranchResponse.model_validate(branch)
    except IntegrityError as error:
        tenant.db.rollback()
        if _is_expected_duplicate_error(error, "uq_branches_salon_code"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Branch code already exists in this salon",
            ) from None
        raise


@router.get("/salons/{salon_id}/branches", response_model=list[BranchResponse])
def list_branches_endpoint(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    active_only: bool = Query(default=False),
) -> list[BranchResponse]:
    """List branches belonging to the current tenant (all roles)."""
    branches = list_branches(tenant.db, tenant.salon.id, active_only=active_only)
    return [BranchResponse.model_validate(branch) for branch in branches]


@router.get("/salons/{salon_id}/branches/{branch_id}", response_model=BranchResponse)
def get_branch_endpoint(
    branch_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> BranchResponse:
    """Get a branch belonging to the current tenant (all roles)."""
    return BranchResponse.model_validate(_get_tenant_branch_or_404(tenant, branch_id))


@router.patch("/salons/{salon_id}/branches/{branch_id}", response_model=BranchResponse)
def update_branch_endpoint(
    branch_id: UUID,
    payload: BranchUpdateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> BranchResponse:
    """Update mutable branch fields (Owner/Manager only)."""
    tenant.require_permission(Permission.MANAGE_STAFF)
    branch = _get_tenant_branch_or_404(tenant, branch_id)
    updated = update_branch(tenant.db, branch, **payload.model_dump(exclude_unset=True))
    tenant.db.commit()
    return BranchResponse.model_validate(updated)


@router.post("/salons/{salon_id}/branches/{branch_id}/activate", response_model=BranchResponse)
def activate_branch_endpoint(
    branch_id: UUID,
    payload: BranchActivateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> BranchResponse:
    """Activate or deactivate a branch (Owner/Manager only)."""
    tenant.require_permission(Permission.MANAGE_STAFF)
    branch = _get_tenant_branch_or_404(tenant, branch_id)
    updated = set_branch_active(tenant.db, branch, payload.is_active)
    tenant.db.commit()
    return BranchResponse.model_validate(updated)
