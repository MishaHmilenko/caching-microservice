import asyncio

import pytest

from cache_service.services.single_flight import SingleFlight


class Loader:
    """Loader whose progress the test controls, recording the batches it was asked for."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.release = asyncio.Event()

    async def __call__(self, keys: list[str]) -> dict[str, str]:
        self.calls.append(list(keys))
        await self.release.wait()
        return {key: key.upper() for key in keys}


async def settle() -> None:
    """Let started tasks run until they block."""
    for _ in range(5):
        await asyncio.sleep(0)


async def test_concurrent_callers_share_one_load():
    flight, loader = SingleFlight(), Loader()

    first = asyncio.create_task(flight.run(["a", "b"], loader))
    await settle()
    second = asyncio.create_task(flight.run(["a", "b"], loader))
    await settle()
    loader.release.set()

    assert await first == await second == {"a": "A", "b": "B"}
    assert loader.calls == [["a", "b"]]


async def test_overlapping_callers_load_only_what_is_not_in_flight():
    flight, loader = SingleFlight(), Loader()

    first = asyncio.create_task(flight.run(["a", "b"], loader))
    await settle()
    second = asyncio.create_task(flight.run(["b", "c"], loader))
    await settle()
    loader.release.set()

    assert await second == {"b": "B", "c": "C"}
    assert await first == {"a": "A", "b": "B"}
    assert loader.calls == [["a", "b"], ["c"]]


async def test_leader_failure_reaches_followers_and_clears_state():
    flight = SingleFlight()
    gate = asyncio.Event()

    async def failing(keys):
        await gate.wait()
        raise ValueError("boom")

    leader = asyncio.create_task(flight.run(["a"], failing))
    await settle()
    follower = asyncio.create_task(flight.run(["a"], failing))
    await settle()
    gate.set()

    for task in (leader, follower):
        with pytest.raises(ValueError, match="boom"):
            await task
    # Nothing stays stuck in flight: a later call leads again and succeeds.
    ready = Loader()
    ready.release.set()
    assert await flight.run(["a"], ready) == {"a": "A"}


async def test_cancelled_leader_does_not_cancel_followers():
    flight, loader = SingleFlight(), Loader()

    leader = asyncio.create_task(flight.run(["a"], loader))
    await settle()
    follower = asyncio.create_task(flight.run(["a"], loader))
    await settle()
    leader.cancel()
    await settle()
    loader.release.set()

    assert await follower == {"a": "A"}
    assert loader.calls == [["a"], ["a"]]  # the follower took over the work


async def test_cancelled_follower_does_not_disturb_the_leader():
    flight, loader = SingleFlight(), Loader()

    leader = asyncio.create_task(flight.run(["a"], loader))
    await settle()
    follower = asyncio.create_task(flight.run(["a"], loader))
    await settle()
    follower.cancel()
    await settle()
    loader.release.set()

    assert await leader == {"a": "A"}
    assert loader.calls == [["a"]]


async def test_loader_that_skips_keys_fails_instead_of_hanging():
    flight = SingleFlight()

    async def lazy(keys):
        return {}

    with pytest.raises(RuntimeError, match="no value"):
        await asyncio.wait_for(flight.run(["a"], lazy), timeout=1)
