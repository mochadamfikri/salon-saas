"""Centralized tenant RBAC policy and target-aware membership rules."""

from enum import Enum

from fastapi import HTTPException, status


class Permission(str, Enum):
    """Tenant-level permissions."""

    VIEW_MEMBERS = "view_members"
    MANAGE_STAFF = "manage_staff"
    MANAGE_MANAGERS = "manage_managers"
    INVITE_STAFF = "invite_staff"
    INVITE_MANAGER = "invite_manager"


class RBACPolicy:
    """Explicit tenant role and membership-administration policy."""

    ROLE_PERMISSIONS: dict[str, set[Permission]] = {
        "owner": {
            Permission.VIEW_MEMBERS,
            Permission.MANAGE_STAFF,
            Permission.MANAGE_MANAGERS,
            Permission.INVITE_STAFF,
            Permission.INVITE_MANAGER,
        },
        "manager": {Permission.VIEW_MEMBERS, Permission.MANAGE_STAFF, Permission.INVITE_STAFF},
        "staff": set(),
    }

    @classmethod
    def require(cls, actor_role: str, permission: Permission) -> None:
        """Require a non-targeted tenant permission."""
        if permission not in cls.ROLE_PERMISSIONS.get(actor_role, set()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )

    @classmethod
    def require_member_mutation(
        cls, actor_role: str, target_role: str, requested_role: str | None = None
    ) -> None:
        """Require authority to update or remove one target membership.

        Owners may manage manager and staff memberships but never owners.
        Managers may manage staff only and may not promote a staff member.
        Staff have no membership-administration authority.
        """
        if target_role == "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Owner membership cannot be mutated",
            )

        if actor_role == "owner":
            return

        if actor_role == "manager" and target_role == "staff":
            if requested_role is None or requested_role == "staff":
                return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
