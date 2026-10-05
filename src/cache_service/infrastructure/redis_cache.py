"""Redis implementation of the cache contract."""

import logging
import random
from collections.abc import Mapping, Sequence

from redis.asyncio import Redis
from redis.exceptions import RedisError

from cache_service.domain.interfaces import Cache

logger = logging.getLogger(__name__)


class RedisCache(Cache):
    """Redis-backed cache that degrades to misses when Redis is unavailable.

    The database is the source of truth, so a cache outage should cost latency, not requests.
    """

    def __init__(self, client: Redis, ttl_seconds: int, ttl_jitter: float = 0.1) -> None:
        """Create the cache.

        :param client: Async Redis client created with ``decode_responses=True``.
        :param ttl_seconds: Average lifetime of the entries written.
        :param ttl_jitter: Fraction of the TTL by which each entry's lifetime is randomly
            shifted, so entries written together do not all expire together.
        """
        # The client must be created with decode_responses=True so values come back as str.
        self._client = client
        self._ttl = ttl_seconds
        self._ttl_jitter = ttl_jitter

    def _expiry(self) -> int:
        """Pick a lifetime for one entry, spread around the configured TTL.

        :return: Seconds until expiry, at least 1.
        """
        spread = self._ttl * self._ttl_jitter
        return max(1, round(random.uniform(self._ttl - spread, self._ttl + spread)))

    async def get(self, key: str) -> str | None:
        """Read an entry; a Redis failure counts as a miss."""
        try:
            return await self._client.get(key)
        except RedisError:
            logger.warning("Cache read failed", exc_info=True)
            return None

    async def get_many(self, keys: Sequence[str]) -> dict[str, str]:
        """Read entries in one round trip; a Redis failure counts as all misses."""
        if not keys:
            return {}
        try:
            values = await self._client.mget(list(keys))
        except RedisError:
            logger.warning("Cache read failed", exc_info=True)
            return {}
        return {k: v for k, v in zip(keys, values, strict=True) if v is not None}

    async def set(self, key: str, value: str) -> None:
        """Write an entry with the TTL; a Redis failure is logged and ignored."""
        try:
            await self._client.set(key, value, ex=self._expiry())
        except RedisError:
            logger.warning("Cache write failed", exc_info=True)

    async def set_many(self, items: Mapping[str, str]) -> None:
        """Write entries with the TTL in one round trip; a Redis failure is logged and ignored."""
        if not items:
            return
        try:
            # MSET cannot set a TTL, so batch individual SETs in one round trip instead.
            async with self._client.pipeline(transaction=False) as pipe:
                for key, value in items.items():
                    pipe.set(key, value, ex=self._expiry())
                await pipe.execute()
        except RedisError:
            logger.warning("Cache write failed", exc_info=True)
