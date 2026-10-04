import pytest

from cache_service.service import PayloadService, payload_id


@pytest.fixture
def service(store, transformer) -> PayloadService:
    return PayloadService(store, transformer)


def test_output_interleaves_transformed_strings(service):
    id_, created = service.create(["a", "b", "c"], ["x", "y", "z"])

    assert created
    assert service.get_output(id_) == "A, X, B, Y, C, Z"


def test_unknown_id_returns_none(service):
    assert service.get_output("missing") is None


def test_identical_request_reuses_id_without_calling_transformer(service, transformer):
    first_id, _ = service.create(["a"], ["b"])
    second_id, created = service.create(["a"], ["b"])

    assert second_id == first_id
    assert not created
    assert len(transformer.calls) == 1


def test_only_unseen_strings_are_transformed(service, transformer):
    service.create(["a", "b"], ["c", "d"])
    service.create(["a", "e"], ["d", "f"])

    assert transformer.calls == [["a", "b", "c", "d"], ["e", "f"]]


def test_duplicates_within_a_request_are_transformed_once(service, transformer):
    id_, _ = service.create(["a", "a"], ["a", "b"])

    assert transformer.calls == [["a", "b"]]
    assert service.get_output(id_) == "A, A, A, B"


def test_fully_cached_strings_in_new_combination_skip_transformer(service, transformer):
    service.create(["a", "b"], ["c", "d"])
    id_, created = service.create(["d", "c"], ["b", "a"])

    assert created
    assert len(transformer.calls) == 1
    assert service.get_output(id_) == "D, B, C, A"


def test_cache_is_shared_between_service_instances(store, transformer):
    id_, _ = PayloadService(store, transformer).create(["a"], ["b"])
    PayloadService(store, transformer).create(["a"], ["c"])

    assert transformer.calls == [["a", "b"], ["c"]]
    assert id_


def test_transformer_result_count_mismatch_is_rejected(store):
    service = PayloadService(store, lambda strings: [])

    with pytest.raises(RuntimeError):
        service.create(["a"], ["b"])


def test_payload_id_depends_on_list_boundaries():
    assert payload_id(["a", "b"], ["c"]) != payload_id(["a"], ["b", "c"])
