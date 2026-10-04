import logging
from collections.abc import Mapping, Sequence

from redis.asyncio import Redis
from redis.exceptions import RedisError

from cache_service.interfaces import Cache

logger = logging.getLogger(__name__)


class RedisCache(Cache):
    """Redis-backed cache that degrades to misses when Redis is unavailable.

    The database is the source of truth, so a cache outage should cost latency, not requests.
    """

    def __init__(self, client: Redis, ttl_seconds: int) -> None:
        # The client must be created with decode_responses=True so values come back as str.
        self._client = client
        self._ttl = ttl_seconds

    async def get(self, key: str) -> str | None:
        try:
            return await self._client.get(key)
        except RedisError:
            logger.warning("Cache read failed", exc_info=True)
            return None

    async def get_many(self, keys: Sequence[str]) -> dict[str, str]:
        if not keys:
            return {}
        try:
            values = await self._client.mget(list(keys))
        except RedisError:
            logger.warning("Cache read failed", exc_info=True)
            return {}
        return {k: v for k, v in zip(keys, values, strict=True) if v is not None}

    async def set(self, key: str, value: str) -> None:
        try:
            await self._client.set(key, value, ex=self._ttl)
        except RedisError:
            logger.warning("Cache write failed", exc_info=True)

    async def set_many(self, items: Mapping[str, str]) -> None:
        if not items:
            return
        try:
            # MSET cannot set a TTL, so batch individual SETs in one round trip instead.
            async with self._client.pipeline(transaction=False) as pipe:
                for key, value in items.items():
                    pipe.set(key, value, ex=self._ttl)
                await pipe.execute()
        except RedisError:
            logger.warning("Cache write failed", exc_info=True)
