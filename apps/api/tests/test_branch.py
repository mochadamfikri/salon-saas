"""Tests for branch domain and API."""

import pytest
from app.models import Branch
from fastapi import status


class TestBranchModel:
    """Test Branch model constraints and relationships."""

    def test_create_branch(self, db_session, salon_factory):
        """Branch can be created with required fields."""
        salon = salon_factory()
        branch = Branch(
            salon_id=salon.id,
            name="Downtown Branch",
            code="downtown",
            timezone="Asia/Jakarta",
            address="Jl. Sudirman 123",
            phone="+62123456789",
        )
        db_session.add(branch)
        db_session.commit()
        db_session.refresh(branch)

        assert branch.id is not None
        assert branch.salon_id == salon.id
        assert branch.name == "Downtown Branch"
        assert branch.code == "downtown"
        assert branch.timezone == "Asia/Jakarta"
        assert branch.address == "Jl. Sudirman 123"
        assert branch.phone == "+62123456789"
        assert branch.is_active is True
        assert branch.created_at is not None
        assert branch.updated_at is not None

    def test_branch_code_unique_per_salon(self, db_session, salon_factory):
        """Branch code must be unique within salon."""
        from sqlalchemy.exc import IntegrityError

        salon = salon_factory()
        branch1 = Branch(
            salon_id=salon.id,
            name="Branch 1",
            code="main",
            timezone="Asia/Jakarta",
        )
        db_session.add(branch1)
        db_session.commit()

        branch2 = Branch(
            salon_id=salon.id,
            name="Branch 2",
            code="main",
            timezone="Asia/Jakarta",
        )
        db_session.add(branch2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_branch_code_reusable_across_salons(self, db_session, salon_factory):
        """Same branch code can exist in different salons."""
        salon1 = salon_factory()
        salon2 = salon_factory()

        branch1 = Branch(
            salon_id=salon1.id,
            name="Main Branch",
            code="main",
            timezone="Asia/Jakarta",
        )
        branch2 = Branch(
            salon_id=salon2.id,
            name="Main Branch",
            code="main",
            timezone="Asia/Jakarta",
        )
        db_session.add_all([branch1, branch2])
        db_session.commit()

        assert branch1.code == branch2.code
        assert branch1.salon_id != branch2.salon_id


class TestBranchService:
    """Test branch business logic."""

    def test_create_branch_success(self, db_session, salon_factory):
        """create_branch creates a branch with valid data."""
        from app.services.branch import create_branch

        salon = salon_factory()
        branch = create_branch(
            db_session,
            salon_id=salon.id,
            name="North Branch",
            code="north",
            timezone="Asia/Jakarta",
            address="Jl. Gatot Subroto 45",
            phone="+62111222333",
        )

        assert branch.id is not None
        assert branch.salon_id == salon.id
        assert branch.name == "North Branch"
        assert branch.code == "north"
        assert branch.timezone == "Asia/Jakarta"
        assert branch.address == "Jl. Gatot Subroto 45"
        assert branch.phone == "+62111222333"
        assert branch.is_active is True

    def test_create_branch_invalid_salon(self, db_session):
        """create_branch raises ValueError for invalid salon."""
        import uuid

        from app.services.branch import create_branch

        with pytest.raises(ValueError, match="Salon not found"):
            create_branch(
                db_session,
                salon_id=uuid.uuid4(),
                name="Branch",
                code="branch",
                timezone="Asia/Jakarta",
            )

    def test_list_branches_all(self, db_session, salon_factory):
        """list_branches returns all branches for a salon."""
        from app.services.branch import create_branch, list_branches

        salon = salon_factory()
        b1 = create_branch(db_session, salon.id, "Branch 1", "b1", "Asia/Jakarta")
        b2 = create_branch(db_session, salon.id, "Branch 2", "b2", "Asia/Jakarta")
        b3 = create_branch(db_session, salon.id, "Branch 3", "b3", "Asia/Jakarta")

        branches = list_branches(db_session, salon.id)
        assert len(branches) == 3
        assert {b.id for b in branches} == {b1.id, b2.id, b3.id}

    def test_list_branches_active_only(self, db_session, salon_factory):
        """list_branches with active_only filters inactive branches."""
        from app.services.branch import create_branch, list_branches, set_branch_active

        salon = salon_factory()
        b1 = create_branch(db_session, salon.id, "Active", "active", "Asia/Jakarta")
        b2 = create_branch(db_session, salon.id, "Inactive", "inactive", "Asia/Jakarta")
        set_branch_active(db_session, b2, False)

        branches = list_branches(db_session, salon.id, active_only=True)
        assert len(branches) == 1
        assert branches[0].id == b1.id

    def test_list_branches_tenant_isolation(self, db_session, salon_factory):
        """list_branches returns only branches for specified salon."""
        from app.services.branch import create_branch, list_branches

        salon1 = salon_factory()
        salon2 = salon_factory()
        b1 = create_branch(db_session, salon1.id, "S1 Branch", "b1", "Asia/Jakarta")
        create_branch(db_session, salon2.id, "S2 Branch", "b2", "Asia/Jakarta")

        branches = list_branches(db_session, salon1.id)
        assert len(branches) == 1
        assert branches[0].id == b1.id

    def test_get_branch_success(self, db_session, salon_factory):
        """get_branch returns branch when found in salon."""
        from app.services.branch import create_branch, get_branch

        salon = salon_factory()
        created = create_branch(db_session, salon.id, "Test", "test", "Asia/Jakarta")

        fetched = get_branch(db_session, created.id, salon.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_get_branch_cross_tenant_404(self, db_session, salon_factory):
        """get_branch returns None for cross-tenant access."""
        from app.services.branch import create_branch, get_branch

        salon1 = salon_factory()
        salon2 = salon_factory()
        branch = create_branch(db_session, salon1.id, "Branch", "br", "Asia/Jakarta")

        fetched = get_branch(db_session, branch.id, salon2.id)
        assert fetched is None

    def test_update_branch_success(self, db_session, salon_factory):
        """update_branch modifies allowed fields."""
        from app.services.branch import create_branch, update_branch

        salon = salon_factory()
        branch = create_branch(db_session, salon.id, "Old Name", "old", "Asia/Jakarta")

        updated = update_branch(
            db_session,
            branch,
            name="New Name",
            timezone="Asia/Singapore",
            address="New Address",
            phone="+6599998888",
        )

        assert updated.name == "New Name"
        assert updated.timezone == "Asia/Singapore"
        assert updated.address == "New Address"
        assert updated.phone == "+6599998888"
        assert updated.code == "old"  # immutable

    def test_set_branch_active(self, db_session, salon_factory):
        """set_branch_active toggles activation status."""
        from app.services.branch import create_branch, set_branch_active

        salon = salon_factory()
        branch = create_branch(db_session, salon.id, "Branch", "br", "Asia/Jakarta")
        assert branch.is_active is True

        deactivated = set_branch_active(db_session, branch, False)
        assert deactivated.is_active is False

        reactivated = set_branch_active(db_session, branch, True)
        assert reactivated.is_active is True


class TestBranchAPI:
    """Test branch API endpoints."""

    def test_create_branch_owner_success(self, client, owner_headers, tenant_context):
        """Owner can create a branch."""
        response = client.post(
            f"/salons/{tenant_context['salon'].id}/branches",
            headers=owner_headers,
            json={
                "name": "East Branch",
                "code": "east",
                "timezone": "Asia/Jakarta",
                "address": "Jl. Thamrin 99",
                "phone": "+62987654321",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "East Branch"
        assert data["code"] == "east"
        assert data["timezone"] == "Asia/Jakarta"
        assert data["address"] == "Jl. Thamrin 99"
        assert data["phone"] == "+62987654321"
        assert data["is_active"] is True
        assert data["salon_id"] == str(tenant_context["salon"].id)

    def test_create_branch_manager_success(self, client, manager_headers, tenant_context):
        """Manager can create a branch."""
        response = client.post(
            f"/salons/{tenant_context['salon'].id}/branches",
            headers=manager_headers,
            json={
                "name": "West Branch",
                "code": "west",
                "timezone": "Asia/Jakarta",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "West Branch"

    def test_create_branch_staff_forbidden(self, client, staff_headers, tenant_context):
        """Staff cannot create branches."""
        response = client.post(
            f"/salons/{tenant_context['salon'].id}/branches",
            headers=staff_headers,
            json={
                "name": "Branch",
                "code": "branch",
                "timezone": "Asia/Jakarta",
            },
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_branch_duplicate_code_conflict(self, client, owner_headers, tenant_context):
        """Creating branch with duplicate code returns 409."""
        payload = {
            "name": "Branch",
            "code": "duplicate",
            "timezone": "Asia/Jakarta",
        }

        response1 = client.post(
            f"/salons/{tenant_context['salon'].id}/branches",
            headers=owner_headers,
            json=payload,
        )
        assert response1.status_code == status.HTTP_201_CREATED

        response2 = client.post(
            f"/salons/{tenant_context['salon'].id}/branches",
            headers=owner_headers,
            json=payload,
        )
        assert response2.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response2.json()["detail"].lower()

    def test_create_branch_reserved_code_rejected(self, client, owner_headers, tenant_context):
        """Reserved branch codes are rejected."""
        response = client.post(
            f"/salons/{tenant_context['salon'].id}/branches",
            headers=owner_headers,
            json={
                "name": "Admin Branch",
                "code": "admin",
                "timezone": "Asia/Jakarta",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_branches_all_roles(self, client, owner_headers, staff_headers, tenant_context):
        """All roles can list branches."""
        # Create test branches
        for i in range(3):
            client.post(
                f"/salons/{tenant_context['salon'].id}/branches",
                headers=owner_headers,
                json={
                    "name": f"Branch {i}",
                    "code": f"b{i}",
                    "timezone": "Asia/Jakarta",
                },
            )

        # Test owner
        response = client.get(
            f"/salons/{tenant_context['salon'].id}/branches",
            headers=owner_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 3

        # Test staff
        response = client.get(
            f"/salons/{tenant_context['salon'].id}/branches",
            headers=staff_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 3

    def test_list_branches_active_filter(self, client, owner_headers, tenant_context, db_session):
        """active_only query parameter filters inactive branches."""
        from app.services.branch import create_branch, set_branch_active

        salon_id = tenant_context["salon"].id
        create_branch(db_session, salon_id, "Active", "active", "Asia/Jakarta")
        b2 = create_branch(db_session, salon_id, "Inactive", "inactive", "Asia/Jakarta")
        set_branch_active(db_session, b2, False)
        db_session.commit()

        response = client.get(
            f"/salons/{salon_id}/branches?active_only=true",
            headers=owner_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        branches = response.json()
        assert len(branches) == 1
        assert branches[0]["code"] == "active"

    def test_get_branch_success(self, client, owner_headers, tenant_context, db_session):
        """Get specific branch by ID."""
        from app.services.branch import create_branch

        salon_id = tenant_context["salon"].id
        branch = create_branch(db_session, salon_id, "Test", "test", "Asia/Jakarta")
        db_session.commit()

        response = client.get(
            f"/salons/{salon_id}/branches/{branch.id}",
            headers=owner_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(branch.id)
        assert data["name"] == "Test"

    def test_get_branch_cross_tenant_404(
        self, client, owner_headers, tenant_context, salon_factory, db_session
    ):
        """Getting branch from another salon returns 404."""
        from app.services.branch import create_branch

        other_salon = salon_factory()
        branch = create_branch(db_session, other_salon.id, "Other", "other", "Asia/Jakarta")
        db_session.commit()

        response = client.get(
            f"/salons/{tenant_context['salon'].id}/branches/{branch.id}",
            headers=owner_headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_branch_owner_success(self, client, owner_headers, tenant_context, db_session):
        """Owner can update branch fields."""
        from app.services.branch import create_branch

        salon_id = tenant_context["salon"].id
        branch = create_branch(db_session, salon_id, "Old", "old", "Asia/Jakarta")
        db_session.commit()

        response = client.patch(
            f"/salons/{salon_id}/branches/{branch.id}",
            headers=owner_headers,
            json={
                "name": "Updated Name",
                "timezone": "Asia/Singapore",
                "address": "New Address",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["timezone"] == "Asia/Singapore"
        assert data["address"] == "New Address"
        assert data["code"] == "old"  # immutable

    def test_update_branch_staff_forbidden(self, client, staff_headers, tenant_context, db_session):
        """Staff cannot update branches."""
        from app.services.branch import create_branch

        salon_id = tenant_context["salon"].id
        branch = create_branch(db_session, salon_id, "Branch", "br", "Asia/Jakarta")
        db_session.commit()

        response = client.patch(
            f"/salons/{salon_id}/branches/{branch.id}",
            headers=staff_headers,
            json={"name": "New Name"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_activate_branch_owner_success(self, client, owner_headers, tenant_context, db_session):
        """Owner can activate/deactivate branches."""
        from app.services.branch import create_branch

        salon_id = tenant_context["salon"].id
        branch = create_branch(db_session, salon_id, "Branch", "br", "Asia/Jakarta")
        db_session.commit()

        # Deactivate
        response = client.post(
            f"/salons/{salon_id}/branches/{branch.id}/activate",
            headers=owner_headers,
            json={"is_active": False},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_active"] is False

        # Reactivate
        response = client.post(
            f"/salons/{salon_id}/branches/{branch.id}/activate",
            headers=owner_headers,
            json={"is_active": True},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_active"] is True

    def test_activate_branch_staff_forbidden(
        self, client, staff_headers, tenant_context, db_session
    ):
        """Staff cannot activate/deactivate branches."""
        from app.services.branch import create_branch

        salon_id = tenant_context["salon"].id
        branch = create_branch(db_session, salon_id, "Branch", "br", "Asia/Jakarta")
        db_session.commit()

        response = client.post(
            f"/salons/{salon_id}/branches/{branch.id}/activate",
            headers=staff_headers,
            json={"is_active": False},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_branch_tenant_isolation_throughout(
        self, client, owner_headers, tenant_context, salon_factory, db_session
    ):
        """All branch endpoints enforce tenant isolation."""
        from app.services.branch import create_branch

        other_salon = salon_factory()
        other_branch = create_branch(db_session, other_salon.id, "Other", "other", "Asia/Jakarta")
        db_session.commit()

        current_salon_id = tenant_context["salon"].id

        # List: only current salon branches
        response = client.get(f"/salons/{current_salon_id}/branches", headers=owner_headers)
        branch_ids = {b["id"] for b in response.json()}
        assert str(other_branch.id) not in branch_ids

        # Get: 404 for other salon
        response = client.get(
            f"/salons/{current_salon_id}/branches/{other_branch.id}",
            headers=owner_headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Update: 404 for other salon
        response = client.patch(
            f"/salons/{current_salon_id}/branches/{other_branch.id}",
            headers=owner_headers,
            json={"name": "Hacked"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Activate: 404 for other salon
        response = client.post(
            f"/salons/{current_salon_id}/branches/{other_branch.id}/activate",
            headers=owner_headers,
            json={"is_active": False},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
