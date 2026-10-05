"""Concurrent requests must not repeat work on the (expensive) transformer."""

import asyncio

from fakes import CountingTransformer


class SlowTransformer(CountingTransformer):
    """Slow enough that concurrent requests genuinely overlap."""

    async def transform(self, strings):
        await asyncio.sleep(0.05)
        return await super().transform(strings)


class FailingOnceTransformer(CountingTransformer):
    async def transform(self, strings):
        await asyncio.sleep(0.05)
        if not self.calls:
            self.calls.append(list(strings))
            raise RuntimeError("boom")
        return await super().transform(strings)


async def test_identical_concurrent_requests_call_transformer_once(client_factory):
    transformer = SlowTransformer()
    body = {"list_1": ["a", "b"], "list_2": ["c", "d"]}

    async with client_factory(transformer) as client:
        responses = await asyncio.gather(*(client.post("/payload", json=body) for _ in range(10)))

    assert len({r.json()["id"] for r in responses}) == 1
    assert [r.status_code for r in responses].count(201) == 1
    assert len(transformer.calls) == 1


async def test_shared_strings_across_different_payloads_are_transformed_once(client_factory):
    transformer = SlowTransformer()
    bodies = [{"list_1": ["shared", f"x{i}"], "list_2": ["common", f"y{i}"]} for i in range(10)]

    async with client_factory(transformer) as client:
        responses = await asyncio.gather(*(client.post("/payload", json=b) for b in bodies))

    assert all(r.status_code == 201 for r in responses)
    transformed = [s for call in transformer.calls for s in call]
    assert transformed.count("shared") == 1
    assert transformed.count("common") == 1
    assert len(transformed) == len(set(transformed))  # nothing transformed twice


async def test_failed_leader_fails_waiting_requests_but_not_later_ones(client_factory):
    transformer = FailingOnceTransformer()
    body = {"list_1": ["a"], "list_2": ["b"]}

    async with client_factory(transformer) as client:
        first = await asyncio.gather(*(client.post("/payload", json=body) for _ in range(5)))
        retry = await client.post("/payload", json=body)

    assert {r.status_code for r in first} == {500}
    assert retry.status_code == 201
