from collections.abc import Iterator, Sequence

import pytest
from sqlmodel import Session

from cache_service.db import create_db_engine, create_tables
from cache_service.transformer import uppercase_transformer


class CountingTransformer:
    """Records every batch it receives so tests can assert on calls to the 'external service'."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, strings: Sequence[str]) -> list[str]:
        self.calls.append(list(strings))
        return uppercase_transformer(strings)


@pytest.fixture
def engine():
    engine = create_db_engine("sqlite://")
    create_tables(engine)
    return engine


@pytest.fixture
def session(engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@pytest.fixture
def transformer() -> CountingTransformer:
    return CountingTransformer()
