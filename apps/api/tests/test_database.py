from app.db import engine
from sqlalchemy import text


def test_database_connection_uses_development_database() -> None:
    with engine.connect() as connection:
        database_name = connection.execute(text("SELECT current_database()")).scalar_one()

    assert database_name == "salon_saas_dev"
