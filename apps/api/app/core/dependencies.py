"""Shared dependencies for FastAPI request scopes.

Provides a single, tested database session lifecycle dependency to prevent
per-route session creation antipatterns.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db import SessionLocal


def get_db() -> Generator[Session]:
    """Yield a database session and safely close it at the end of the request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
