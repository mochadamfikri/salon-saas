"""Database engine and ORM metadata foundation."""

from sqlalchemy import Column, DateTime, MetaData, String, Table, create_engine, func
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Base class for future ORM models."""

    metadata = metadata


platform_metadata = Table(
    "platform_metadata",
    metadata,
    Column("key", String(100), primary_key=True),
    Column("value", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
