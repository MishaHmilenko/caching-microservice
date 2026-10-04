from collections.abc import Sequence

import fakeredis
import pytest

from cache_service.store import RedisStore
from cache_service.transformer import uppercase_transformer


class CountingTransformer:
    """Records every batch it receives so tests can assert on calls to the 'external service'."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, strings: Sequence[str]) -> list[str]:
        self.calls.append(list(strings))
        return uppercase_transformer(strings)


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def store(redis_client) -> RedisStore:
    return RedisStore(redis_client)


@pytest.fixture
def transformer() -> CountingTransformer:
    return CountingTransformer()
