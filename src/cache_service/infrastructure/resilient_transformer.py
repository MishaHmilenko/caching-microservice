"""Fault-tolerance wrapper for the external transformer."""

import asyncio
import logging
import random
from collections.abc import Sequence

from cache_service.domain.errors import TransformerUnavailableError
from cache_service.domain.interfaces import Transformer

logger = logging.getLogger(__name__)

# Only failures that a repeat attempt can plausibly fix are retried; anything else is a bug or a
# bad response and retrying would just repeat it.
RETRYABLE_ERRORS = (TimeoutError, ConnectionError)


class ResilientTransformer(Transformer):
    """Adds a timeout, bounded retries, a concurrency limit and batch splitting to a transformer.

    A slow or flaky upstream must degrade into a fast, clear 503 rather than pile up requests
    or hang them.
    """

    def __init__(
        self,
        transformer: Transformer,
        *,
        timeout_seconds: float,
        max_attempts: int,
        backoff_seconds: float,
        max_concurrency: int,
        batch_size: int,
    ) -> None:
        """Wrap a transformer.

        :param transformer: The transformer to protect.
        :param timeout_seconds: Time allowed for one attempt on one batch.
        :param max_attempts: Attempts per batch, including the first.
        :param backoff_seconds: Base delay before a retry; doubles each time, with jitter.
        :param max_concurrency: Upstream calls allowed in flight at once.
        :param batch_size: Largest batch sent in a single upstream call.
        """
        self._transformer = transformer
        self._timeout = timeout_seconds
        self._max_attempts = max_attempts
        self._backoff = backoff_seconds
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._batch_size = batch_size

    async def transform(self, strings: Sequence[str]) -> list[str]:
        """Transform strings in bounded batches, concurrently, preserving order.

        :param strings: Strings to transform.
        :return: One result per input, in the same order.
        :raises TransformerUnavailableError: If a batch still fails after all attempts.
        """
        batches = [
            strings[start : start + self._batch_size]
            for start in range(0, len(strings), self._batch_size)
        ]
        results = await asyncio.gather(*(self._transform_batch(batch) for batch in batches))
        return [result for batch in results for result in batch]

    async def _transform_batch(self, batch: Sequence[str]) -> list[str]:
        """Transform one batch, retrying transient failures with exponential backoff."""
        for attempt in range(1, self._max_attempts + 1):
            try:
                # The semaphore is held per attempt, not while backing off, so a sleeping retry
                # does not block other batches.
                async with self._semaphore, asyncio.timeout(self._timeout):
                    return await self._transformer.transform(batch)
            except RETRYABLE_ERRORS as error:
                if attempt == self._max_attempts:
                    raise TransformerUnavailableError from error
                delay = self._backoff * 2 ** (attempt - 1) * random.uniform(0.5, 1.5)
                logger.warning(
                    "Transformer attempt %d/%d failed (%r); retrying in %.2fs",
                    attempt,
                    self._max_attempts,
                    error,
                    delay,
                )
                await asyncio.sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover
