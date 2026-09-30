"""Environment-based application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Runtime settings loaded from the project environment file."""

    app_env: str = "development"
    app_name: str = "Salon SaaS Platform"
    database_url: str
    redis_url: str
    log_level: str = "INFO"

    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "salon-saas-api"
    jwt_audience: str = "salon-saas-web"
    access_token_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_days: int = Field(default=30, ge=1, le=90)
    password_reset_minutes: int = Field(default=60, ge=5, le=1440)
    invitation_days: int = Field(default=7, ge=1, le=30)

    # Redis fixed-window rate limiting (requests per 60-second window per IP).
    rate_limit_enabled: bool = True
    rate_limit_register: int = Field(default=5, ge=1)
    rate_limit_login: int = Field(default=10, ge=1)
    rate_limit_refresh: int = Field(default=60, ge=1)
    rate_limit_password_reset: int = Field(default=5, ge=1)
    rate_limit_invitation_accept: int = Field(default=20, ge=1)

    # Trusted proxy configuration for X-Forwarded-For parsing.
    # PRODUCTION: Set to the internal IP(s) of your reverse proxy (Nginx/HAProxy).
    # EMPTY (default): Use request.client.host (direct TCP peer) — safe for
    # development and for production deployments where the app is NOT behind
    # a proxy. Never trust X-Forwarded-For from untrusted sources.
    trusted_proxies: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached process-level settings."""
    return Settings()
