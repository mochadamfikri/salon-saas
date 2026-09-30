"""FastAPI application entry point."""

import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.routers.auth import router as auth_router

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url=None,
)
app.include_router(auth_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return process liveness without exposing infrastructure details."""
    return {"status": "ok"}
