"""FastAPI application entry point."""

import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.routers.auth import router as auth_router
from app.routers.invitation import router as invitation_router
from app.routers.password_reset import router as password_reset_router
from app.routers.service import router as service_router
from app.routers.staff_profile import router as staff_profile_router
from app.routers.tenant import router as tenant_router

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url=None,
)
app.include_router(auth_router)
app.include_router(invitation_router)
app.include_router(password_reset_router)
app.include_router(service_router)
app.include_router(staff_profile_router)
app.include_router(tenant_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return process liveness without exposing infrastructure details."""
    return {"status": "ok"}
