"""Environment-based application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Runtime settings loaded from the project environment file."""

    app_env: str = "development"
    app_name: str = "Salon SaaS Platform"
    database_url: str
    redis_url: str
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached process-level settings."""
    return Settings()
