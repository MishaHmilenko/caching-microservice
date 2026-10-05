"""Coalescing of concurrent work on the same keys."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence

Loader = Callable[[list[str]], Awaitable[dict[str, str]]]


class SingleFlight:
    """Makes concurrent requests for the same key share one computation.

    Without it, N simultaneous requests that all miss the cache on the same string would each
    call the expensive transformer. Here the first becomes the *leader* for that key and the
    rest wait for its result. State is per process; spanning replicas would need a
    distributed lock.
    """

    def __init__(self) -> None:
        """Create an instance with nothing in flight."""
        self._in_flight: dict[str, asyncio.Future[str]] = {}

    async def run(self, keys: Sequence[str], loader: Loader) -> dict[str, str]:
        """Resolve keys, computing only those nobody else is already computing.

        :param keys: Distinct keys to resolve.
        :param loader: Coroutine function computing a batch of keys. It is called at most once
            per call of :meth:`run`, and only with the keys this caller leads.
        :return: Mapping of every key to its value.
        :raises Exception: Whatever the leader's loader raised, for followers too.
        """
        following = {key: self._in_flight[key] for key in keys if key in self._in_flight}
        leading = [key for key in keys if key not in following]

        results: dict[str, str] = {}
        if leading:
            results.update(await self._lead(leading, loader))
        retry: list[str] = []
        for key, future in following.items():
            try:
                # Shielded so cancelling this follower does not cancel the shared future.
                results[key] = await asyncio.shield(future)
            except asyncio.CancelledError:
                if not future.cancelled():
                    raise  # this follower itself was cancelled
                retry.append(key)  # the leader was cancelled; do the work ourselves
        if retry:
            results.update(await self.run(retry, loader))
        return results

    async def _lead(self, keys: list[str], loader: Loader) -> dict[str, str]:
        """Run the loader for keys this caller leads and publish the outcome to followers."""
        futures = {key: asyncio.get_running_loop().create_future() for key in keys}
        self._in_flight.update(futures)
        try:
            loaded = await loader(keys)
            if missing := set(keys) - loaded.keys():
                # Unresolved futures would leave followers waiting forever.
                raise RuntimeError(f"Loader returned no value for {sorted(missing)}")
        except BaseException as error:
            for key, future in futures.items():
                del self._in_flight[key]
                if isinstance(error, asyncio.CancelledError):
                    future.cancel()
                else:
                    future.set_exception(error)
                    future.exception()  # mark retrieved: there may be no followers
            raise
        for key, future in futures.items():
            del self._in_flight[key]
            future.set_result(loaded[key])
        return loaded
