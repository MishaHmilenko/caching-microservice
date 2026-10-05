"""Behaviour of the Redis layer in front of Postgres, verified against both for real."""

from sqlalchemy import delete

from cache_service.core.hashing import sha256_hex
from cache_service.infrastructure.models import PayloadRow, TransformedStringRow


def string_key(source):
    return f"string:{sha256_hex(source)}"


BODY = {"list_1": ["a", "b"], "list_2": ["c", "d"]}


async def test_created_entries_are_cached_with_ttl(client, redis, settings):
    id_ = (await client.post("/payload", json=BODY)).json()["id"]

    assert await redis.get(f"payload:{id_}") == "A, C, B, D"
    assert await redis.get(string_key("a")) == "A"
    assert 0 < await redis.ttl(string_key("a")) <= settings.cache_ttl_seconds * 1.1


async def test_cache_keys_have_bounded_size_regardless_of_text_length(client, redis):
    long_text = "x" * 1000
    await client.post("/payload", json={"list_1": [long_text], "list_2": ["b"]})

    assert max(len(key) for key in await redis.keys("string:*")) == len("string:") + 64


async def test_ttls_are_spread_so_entries_do_not_expire_together(client, redis, settings):
    strings = [f"s{i}" for i in range(50)]
    await client.post("/payload", json={"list_1": strings, "list_2": strings})

    ttls = {await redis.ttl(string_key(s)) for s in strings}

    assert len(ttls) > 1
    spread = settings.cache_ttl_seconds * settings.cache_ttl_jitter
    assert all(
        settings.cache_ttl_seconds - spread - 1 <= ttl <= settings.cache_ttl_seconds + spread
        for ttl in ttls
    )


async def test_flushed_cache_is_rebuilt_from_postgres(client, redis, transformer):
    id_ = (await client.post("/payload", json=BODY)).json()["id"]
    await redis.flushdb()

    response = await client.get(f"/payload/{id_}")

    assert response.json() == {"output": "A, C, B, D"}
    assert await redis.get(f"payload:{id_}") == "A, C, B, D"  # repopulated on read
    assert len(transformer.calls) == 1


async def test_flushed_cache_does_not_cause_retransformation(client, redis, transformer):
    await client.post("/payload", json=BODY)
    await redis.flushdb()

    await client.post("/payload", json={"list_1": ["d", "c"], "list_2": ["b", "a"]})

    assert len(transformer.calls) == 1


async def test_reads_are_served_from_cache(client, engine):
    id_ = (await client.post("/payload", json=BODY)).json()["id"]
    async with engine.begin() as connection:
        await connection.execute(delete(PayloadRow))
        await connection.execute(delete(TransformedStringRow))

    # Only Redis still has the data, so a successful read proves it came from there.
    assert (await client.get(f"/payload/{id_}")).json() == {"output": "A, C, B, D"}


async def test_service_keeps_working_when_redis_is_down(client_factory, transformer):
    async with client_factory(transformer, redis_url="redis://127.0.0.1:1/0") as client:
        created = await client.post("/payload", json=BODY)
        again = await client.post("/payload", json=BODY)
        read = await client.get(f"/payload/{created.json()['id']}")

    assert read.json() == {"output": "A, C, B, D"}
    assert again.json()["id"] == created.json()["id"]
    assert len(transformer.calls) == 1  # Postgres alone still prevents recomputation
