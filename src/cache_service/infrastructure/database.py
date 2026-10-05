"""Database engine, session and schema setup."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cache_service.infrastructure.models import Base

# Arbitrary constant naming the schema-setup lock; every replica must use the same one.
SCHEMA_LOCK_ID = 7_351_204_001


def create_engine(url: str) -> AsyncEngine:
    """Create the async engine.

    :param url: SQLAlchemy database URL (an async driver such as ``postgresql+asyncpg``).
    :return: The engine; the caller owns it and must dispose of it.
    """
    # Validate connections on checkout so a restarted database doesn't surface as errors.
    return create_async_engine(url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a factory of sessions bound to the engine.

    :param engine: Engine the sessions run on.
    :return: A session factory whose sessions keep loaded objects usable after commit.
    """
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(engine: AsyncEngine) -> None:
    """Create any missing tables; safe to call from several replicas at once.

    :param engine: Engine of the target database.
    """
    # Shortcut: create_all instead of migrations; adopt Alembic once the schema evolves.
    async with engine.begin() as connection:
        # Concurrent CREATE TABLE IF NOT EXISTS is not atomic in Postgres: replicas starting
        # together collide on the catalog. A transaction-scoped advisory lock serialises them
        # and is released automatically on commit or failure.
        await connection.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": SCHEMA_LOCK_ID})
        await connection.run_sync(Base.metadata.create_all)
