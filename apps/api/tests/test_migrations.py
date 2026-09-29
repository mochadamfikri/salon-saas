import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from app.core.config import get_settings
from app.db import engine
from sqlalchemy import text
from sqlalchemy.engine import make_url

API_DIRECTORY = Path(__file__).resolve().parents[1]


def _database_url_for(database: str) -> str:
    configured_url = make_url(get_settings().database_url)
    return configured_url.set(database=database).render_as_string(hide_password=False)


def test_migrations_upgrade_configured_development_database_to_head() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIRECTORY,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert revision == "20260929_0001"


def test_migrations_upgrade_clean_database_to_head() -> None:
    database_name = f"salon_saas_migration_{uuid4().hex[:12]}"
    admin_url = make_url(get_settings().database_url).set(database="postgres")
    clean_database_url = _database_url_for(database_name)
    connection_kwargs = {
        "host": admin_url.host,
        "port": admin_url.port,
        "user": admin_url.username,
        "password": admin_url.password,
        "dbname": admin_url.database,
        "autocommit": True,
    }

    with psycopg.connect(**connection_kwargs) as connection:
        connection.execute(f'CREATE DATABASE "{database_name}"')

    try:
        environment = os.environ.copy()
        environment["DATABASE_URL"] = clean_database_url
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=API_DIRECTORY,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr

        clean_connection_kwargs = {**connection_kwargs, "dbname": database_name}
        with psycopg.connect(**clean_connection_kwargs) as connection:
            revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
            table = connection.execute("SELECT to_regclass('public.platform_metadata')").fetchone()

        assert revision == ("20260929_0001",)
        assert table == ("platform_metadata",)
    finally:
        with psycopg.connect(**connection_kwargs) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
                (database_name,),
            )
            connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
