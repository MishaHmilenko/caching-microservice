import asyncio

import pytest
from sqlalchemy import func, select

from cache_service.domain.payload import interleave, payload_id
from cache_service.infrastructure.models import PayloadRow, TransformedStringRow

SAMPLE = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}
SAMPLE_OUTPUT = (
    "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
)


async def test_create_then_read_round_trip(client):
    created = await client.post("/payload", json=SAMPLE)

    assert created.status_code == 201
    response = await client.get(f"/payload/{created.json()['id']}")
    assert response.status_code == 200
    assert response.json() == {"output": SAMPLE_OUTPUT}


async def test_repeated_post_returns_same_id_and_skips_transformer(client, transformer):
    first = await client.post("/payload", json=SAMPLE)
    second = await client.post("/payload", json=SAMPLE)

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(transformer.calls) == 1


async def test_only_unseen_strings_are_transformed(client, transformer):
    await client.post("/payload", json={"list_1": ["a", "b"], "list_2": ["c", "d"]})
    await client.post("/payload", json={"list_1": ["a", "e"], "list_2": ["d", "f"]})

    assert transformer.calls == [["a", "b", "c", "d"], ["e", "f"]]


async def test_duplicates_within_a_request_are_transformed_once(client, transformer):
    created = await client.post("/payload", json={"list_1": ["a", "a"], "list_2": ["a", "b"]})

    assert transformer.calls == [["a", "b"]]
    response = await client.get(f"/payload/{created.json()['id']}")
    assert response.json() == {"output": "A, A, A, B"}


async def test_known_strings_in_new_combination_skip_transformer(client, transformer):
    await client.post("/payload", json={"list_1": ["a", "b"], "list_2": ["c", "d"]})
    created = await client.post("/payload", json={"list_1": ["d", "c"], "list_2": ["b", "a"]})

    assert created.status_code == 201
    assert len(transformer.calls) == 1
    assert (await client.get(f"/payload/{created.json()['id']}")).json() == {"output": "D, B, C, A"}


async def test_unknown_payload_is_404(client):
    assert (await client.get("/payload/nope")).status_code == 404


async def test_length_mismatch_is_rejected_by_business_rule(client, transformer):
    response = await client.post("/payload", json={"list_1": ["a"], "list_2": ["b", "c"]})

    assert response.status_code == 422
    assert response.json() == {"detail": "list_1 and list_2 must have the same length"}
    assert transformer.calls == []


@pytest.mark.parametrize(
    "body",
    [
        {"list_1": ["a"], "list_2": ["b", "c"]},
        {"list_1": [], "list_2": []},
        {"list_1": ["a"]},
        {"list_1": [1], "list_2": ["b"]},
        {"list_1": ["x" * 1001], "list_2": ["b"]},
    ],
)
async def test_invalid_input_is_rejected(client, transformer, body):
    assert (await client.post("/payload", json=body)).status_code == 422
    assert transformer.calls == []


async def test_data_is_persisted_in_postgres(client, engine):
    await client.post("/payload", json={"list_1": ["a", "b"], "list_2": ["c", "d"]})

    async with engine.connect() as connection:
        strings = await connection.scalar(select(func.count()).select_from(TransformedStringRow))
        output = await connection.scalar(select(PayloadRow.output))
    assert strings == 4
    assert output == "A, C, B, D"


async def test_state_survives_app_restart(client_factory, transformer):
    async with client_factory(transformer) as first:
        id_ = (await first.post("/payload", json=SAMPLE)).json()["id"]
    async with client_factory(transformer) as second:
        assert (await second.post("/payload", json=SAMPLE)).json()["id"] == id_
        assert (await second.get(f"/payload/{id_}")).status_code == 200

    assert len(transformer.calls) == 1


async def test_concurrent_identical_requests_create_one_payload(client, engine):
    responses = await asyncio.gather(*(client.post("/payload", json=SAMPLE) for _ in range(20)))

    assert {r.json()["id"] for r in responses} == {payload_id(**SAMPLE)}
    assert [r.status_code for r in responses].count(201) == 1
    async with engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(PayloadRow)) == 1


async def test_transformer_result_count_mismatch_fails_without_storing(client_factory, engine):
    class BrokenTransformer:
        async def transform(self, strings):
            return []

    async with client_factory(BrokenTransformer()) as client:
        with pytest.raises(RuntimeError, match="different number"):
            await client.post("/payload", json=SAMPLE)

    async with engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(PayloadRow)) == 0


def test_interleave_alternates_items():
    assert interleave(["a", "b"], ["x", "y"]) == ["a", "x", "b", "y"]


def test_payload_id_depends_on_list_boundaries():
    assert payload_id(["a", "b"], ["c"]) != payload_id(["a"], ["b", "c"])
