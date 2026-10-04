import pytest
from fastapi.testclient import TestClient

from cache_service.main import create_app

SAMPLE = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}


@pytest.fixture
def client(transformer, redis_client):
    with TestClient(create_app(transformer=transformer, redis_client=redis_client)) as client:
        yield client


def test_create_then_read_round_trip(client):
    created = client.post("/payload", json=SAMPLE)

    assert created.status_code == 201
    response = client.get(f"/payload/{created.json()['id']}")
    assert response.status_code == 200
    assert response.json() == {
        "output": "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, "
        "THIRD STRING, LAST STRING"
    }


def test_repeated_post_returns_same_id_and_skips_transformer(client, transformer):
    first = client.post("/payload", json=SAMPLE)
    second = client.post("/payload", json=SAMPLE)

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(transformer.calls) == 1


def test_unknown_payload_is_404(client):
    assert client.get("/payload/nope").status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"list_1": ["a"], "list_2": ["b", "c"]},
        {"list_1": [], "list_2": []},
        {"list_1": ["a"]},
        {"list_1": [1], "list_2": ["b"]},
    ],
)
def test_invalid_input_is_rejected(client, transformer, body):
    assert client.post("/payload", json=body).status_code == 422
    assert transformer.calls == []


def test_cache_is_shared_across_app_instances(transformer, redis_client):
    """A second app on the same Redis stands in for a restart or another replica."""
    with TestClient(create_app(transformer=transformer, redis_client=redis_client)) as first:
        id_ = first.post("/payload", json=SAMPLE).json()["id"]
    with TestClient(create_app(transformer=transformer, redis_client=redis_client)) as second:
        assert second.post("/payload", json=SAMPLE).json()["id"] == id_
        assert second.get(f"/payload/{id_}").status_code == 200

    assert len(transformer.calls) == 1
