"""Shared pytest fixtures with transaction-isolated database access."""

from collections.abc import Generator
from types import SimpleNamespace

import pytest
from app.core.dependencies import get_db
from app.db import engine
from app.main import app
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
        lambda: SimpleNamespace(rate_limit_enabled=False),
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
