"""Tenant context and RBAC dependencies."""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.dependencies import get_db
from app.models import Salon, SalonMembership, User


class TenantContext:
    """Validated tenant context for multi-tenant operations.

    Provides active salon, active membership, and user details.
    """

    def __init__(self, salon: Salon, membership: SalonMembership, user: User, db: Session):
        self.salon = salon
        self.membership = membership
        self.user = user
        self.db = db

    @property
    def role(self) -> str:
        """User's role in this salon."""
        return self.membership.role

    def require_owner(self) -> None:
        """Raise 403 if the current user is not an owner."""
        if self.role != "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Owner role required",
            )

    def require_owner_or_manager(self) -> None:
        """Raise 403 if the current user is not owner or manager."""
        if self.role not in ("owner", "manager"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Owner or manager role required",
            )


def get_tenant_context(
    salon_id: Annotated[uuid.UUID, Path()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TenantContext:
    """Load and validate active salon membership for the current user.

    Verifies:
    - Salon exists
    - User has active membership in this salon
    - Membership is not suspended

    Returns:
        TenantContext with salon, membership, user, db.

    Raises:
        HTTPException 403: No active membership or access denied.
        HTTPException 404: Salon not found.
    """
    salon = db.get(Salon, salon_id)
    if not salon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Salon not found",
        )

    membership = (
        db.query(SalonMembership)
        .filter(
            SalonMembership.salon_id == salon_id,
            SalonMembership.user_id == user.id,
            SalonMembership.status == "active",
        )
        .first()
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: no active membership in this salon",
        )

    return TenantContext(salon=salon, membership=membership, user=user, db=db)
