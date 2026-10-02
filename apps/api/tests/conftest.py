"""Shared pytest fixtures with transaction-isolated database access."""

import uuid
from collections.abc import Callable, Generator
from types import SimpleNamespace

import pytest
from app.core.dependencies import get_db
from app.core.security import hash_password
from app.db import engine
from app.main import app
from app.models import Salon, SalonMembership, User
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture(autouse=True)
def _disable_rate_limiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable Redis rate limiting for the general suite.

    The shared TestClient peer IP would otherwise exhaust the per-minute
    buckets across unrelated tests. tests/test_rate_limit.py re-enables the
    limiter with fakeredis for its own coverage.
    """
    monkeypatch.setattr(
        "app.core.rate_limit.get_settings",
        lambda: SimpleNamespace(rate_limit_enabled=False, trusted_proxies=[]),
    )


@pytest.fixture(scope="function")
def db_session() -> Generator[Session]:
    """Yield an API-overridden session rolled back after every test.

    The outer database transaction is never committed, so endpoint tests cannot
    persist fixtures or delete schema/data in the development database.
    """
    connection: Connection = engine.connect()
    outer_transaction = connection.begin()
    session = sessionmaker(bind=connection, expire_on_commit=False)()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(active_session: Session, transaction: object) -> None:
        parent = getattr(transaction, "_parent", None)
        nested = getattr(transaction, "nested", False)
        if nested and parent is not None and not getattr(parent, "nested", False):
            active_session.begin_nested()

    def override_get_db() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture
def user_factory(db_session: Session) -> Callable[[], User]:
    """Factory for creating test users."""

    def _create_user(
        email: str | None = None,
        password_hash: str = "hashed_password",
    ) -> User:
        user = User(
            email=email or f"user-{uuid.uuid4()}@example.com",
            password_hash=password_hash,
        )
        db_session.add(user)
        db_session.flush()
        db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture
def salon_factory(db_session: Session, user_factory: Callable[[], User]) -> Callable[[], Salon]:
    """Factory for creating test salons."""

    def _create_salon(
        name: str | None = None,
        slug: str | None = None,
        creator: User | None = None,
    ) -> Salon:
        if creator is None:
            creator = user_factory()
        unique_suffix = str(uuid.uuid4())[:8]
        salon = Salon(
            name=name or f"Test Salon {unique_suffix}",
            slug=slug or f"test-salon-{unique_suffix}",
            created_by_user_id=creator.id,
        )
        db_session.add(salon)
        db_session.flush()
        db_session.refresh(salon)
        return salon

    return _create_salon


@pytest.fixture
def client() -> TestClient:
    """Provide FastAPI TestClient."""
    return TestClient(app)


@pytest.fixture
def tenant_context(db_session: Session) -> dict:
    """Create a complete tenant context with owner, manager, staff users and salon."""
    owner = User(
        email=f"owner-{uuid.uuid4()}@example.com",
        password_hash=hash_password("SecurePass123"),
        is_active=True,
    )
    manager = User(
        email=f"manager-{uuid.uuid4()}@example.com",
        password_hash=hash_password("SecurePass123"),
        is_active=True,
    )
    staff = User(
        email=f"staff-{uuid.uuid4()}@example.com",
        password_hash=hash_password("SecurePass123"),
        is_active=True,
    )
    db_session.add_all([owner, manager, staff])
    db_session.flush()

    salon = Salon(
        name=f"Test Salon {uuid.uuid4()}",
        slug=f"test-{uuid.uuid4()}",
        created_by_user_id=owner.id,
    )
    db_session.add(salon)
    db_session.flush()

    owner_membership = SalonMembership(salon_id=salon.id, user_id=owner.id, role="owner")
    manager_membership = SalonMembership(salon_id=salon.id, user_id=manager.id, role="manager")
    staff_membership = SalonMembership(salon_id=salon.id, user_id=staff.id, role="staff")
    db_session.add_all([owner_membership, manager_membership, staff_membership])
    db_session.commit()

    return {
        "salon": salon,
        "owner": owner,
        "manager": manager,
        "staff": staff,
        "owner_membership": owner_membership,
        "manager_membership": manager_membership,
        "staff_membership": staff_membership,
    }


@pytest.fixture
def owner_headers(client: TestClient, tenant_context: dict) -> dict[str, str]:
    """Get authorization headers for owner role."""
    response = client.post(
        "/auth/login",
        json={"email": tenant_context["owner"].email, "password": "SecurePass123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def manager_headers(client: TestClient, tenant_context: dict) -> dict[str, str]:
    """Get authorization headers for manager role."""
    response = client.post(
        "/auth/login",
        json={"email": tenant_context["manager"].email, "password": "SecurePass123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def staff_headers(client: TestClient, tenant_context: dict) -> dict[str, str]:
    """Get authorization headers for staff role."""
    response = client.post(
        "/auth/login",
        json={"email": tenant_context["staff"].email, "password": "SecurePass123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
