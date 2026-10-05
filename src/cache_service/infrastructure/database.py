"""Database engine and session setup. The schema itself is managed by Alembic migrations."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


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
