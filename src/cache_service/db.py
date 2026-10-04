from sqlalchemy import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine


def create_db_engine(url: str) -> Engine:
    if not url.startswith("sqlite"):
        return create_engine(url)

    # FastAPI runs sync endpoints in a thread pool, so connections cross threads.
    kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if url in ("sqlite://", "sqlite:///:memory:"):
        # An in-memory database is per-connection; share a single one so tables stay visible.
        kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


def create_tables(engine: Engine) -> None:
    # Importing registers the table models on SQLModel.metadata.
    from cache_service import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
