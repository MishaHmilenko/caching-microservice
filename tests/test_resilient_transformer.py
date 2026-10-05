import asyncio

import pytest

from cache_service.domain.errors import TransformerUnavailableError
from cache_service.infrastructure.resilient_transformer import ResilientTransformer
from fakes import CountingTransformer


def wrap(inner, **overrides) -> ResilientTransformer:
    options = {
        "timeout_seconds": 1.0,
        "max_attempts": 3,
        "backoff_seconds": 0.001,
        "max_concurrency": 4,
        "batch_size": 100,
    } | overrides
    return ResilientTransformer(inner, **options)


class FlakyTransformer(CountingTransformer):
    """Fails the first ``failures`` calls with ``error``, then behaves."""

    def __init__(self, failures: int, error: Exception) -> None:
        super().__init__()
        self._failures = failures
        self._error = error

    async def transform(self, strings):
        if len(self.calls) < self._failures:
            self.calls.append(list(strings))
            raise self._error
        return await super().transform(strings)


async def test_transient_failures_are_retried():
    inner = FlakyTransformer(failures=2, error=ConnectionError("down"))

    assert await wrap(inner).transform(["a"]) == ["A"]
    assert len(inner.calls) == 3


async def test_gives_up_after_max_attempts_with_unavailable_error():
    inner = FlakyTransformer(failures=99, error=ConnectionError("down"))

    with pytest.raises(TransformerUnavailableError) as raised:
        await wrap(inner, max_attempts=3).transform(["a"])

    assert len(inner.calls) == 3
    assert isinstance(raised.value.__cause__, ConnectionError)


async def test_slow_attempts_time_out_and_are_retried():
    class Hanging(CountingTransformer):
        async def transform(self, strings):
            self.calls.append(list(strings))
            await asyncio.sleep(10)

    inner = Hanging()

    with pytest.raises(TransformerUnavailableError):
        await wrap(inner, timeout_seconds=0.01, max_attempts=2).transform(["a"])

    assert len(inner.calls) == 2


async def test_unexpected_errors_are_not_retried():
    inner = FlakyTransformer(failures=99, error=ValueError("bug"))

    with pytest.raises(ValueError, match="bug"):
        await wrap(inner).transform(["a"])

    assert len(inner.calls) == 1


async def test_large_input_is_split_into_batches_and_order_is_kept():
    inner = CountingTransformer()
    strings = [f"s{i}" for i in range(250)]

    result = await wrap(inner, batch_size=100).transform(strings)

    assert [len(call) for call in inner.calls] == [100, 100, 50]
    assert result == [s.upper() for s in strings]


async def test_concurrency_is_bounded():
    running = peak = 0

    class Tracking(CountingTransformer):
        async def transform(self, strings):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.01)
            running -= 1
            return await super().transform(strings)

    await wrap(Tracking(), batch_size=1, max_concurrency=3).transform([str(i) for i in range(12)])

    assert peak == 3
