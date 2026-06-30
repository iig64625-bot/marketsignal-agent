"""Tests for the retry utility."""
from __future__ import annotations

import httpx
import pytest

from signalpulse.utils.retry import (
    DEFAULT_RETRYABLE,
    retry_with_backoff,
    retry_with_backoff_async,
)


async def test_succeeds_first_try() -> None:
    calls = []

    async def good(x: int) -> int:
        calls.append(x)
        return x * 2

    result = await retry_with_backoff_async(good, 5, max_retries=3)
    assert result == 10
    assert len(calls) == 1


async def test_retries_then_succeeds() -> None:
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("transient")
        return "ok"

    result = await retry_with_backoff_async(flaky, max_retries=5, base_delay=0.01)
    assert result == "ok"
    assert calls["n"] == 3


async def test_gives_up_after_max_retries() -> None:
    calls = {"n": 0}

    async def always_fails() -> None:
        calls["n"] += 1
        raise ConnectionError("nope")

    with pytest.raises(ConnectionError):
        await retry_with_backoff_async(always_fails, max_retries=2, base_delay=0.01)
    assert calls["n"] == 2


async def test_does_not_retry_non_retryable() -> None:
    calls = {"n": 0}

    async def boom() -> None:
        calls["n"] += 1
        raise ValueError("not in retryable list")

    with pytest.raises(ValueError):
        await retry_with_backoff_async(boom, max_retries=5, base_delay=0.01)
    assert calls["n"] == 1


async def test_decorator_form() -> None:
    @retry_with_backoff(max_retries=3, base_delay=0.01)
    async def fn() -> int:
        return 42

    assert await fn() == 42


async def test_exponential_delay_increases() -> None:
    delays_seen = []

    def on_retry(attempt, exc, delay):
        delays_seen.append(delay)

    async def always() -> None:
        raise ConnectionError("x")

    with pytest.raises(ConnectionError):
        await retry_with_backoff_async(
            always, max_retries=3, base_delay=0.1, max_delay=10.0, on_retry=on_retry
        )
    assert len(delays_seen) == 2
    assert delays_seen[0] <= 0.1
    assert delays_seen[1] <= 0.2


async def test_max_delay_cap() -> None:
    delays = []

    def hook(attempt, exc, delay):
        delays.append(delay)

    async def always() -> None:
        raise ConnectionError("x")

    with pytest.raises(ConnectionError):
        await retry_with_backoff_async(
            always, max_retries=3, base_delay=1.0, max_delay=0.05, on_retry=hook
        )
    for d in delays:
        assert d <= 0.05


async def test_invalid_max_retries() -> None:
    async def never() -> None:
        raise AssertionError("should not run")

    with pytest.raises(ValueError):
        await retry_with_backoff_async(never, max_retries=0)


async def test_http_status_error_retryable() -> None:
    calls = {"n": 0}

    async def status_err() -> None:
        calls["n"] += 1
        request = httpx.Request("GET", "http://x")
        response = httpx.Response(500, request=request)
        raise httpx.HTTPStatusError("500", request=request, response=response)

    with pytest.raises(httpx.HTTPStatusError):
        await retry_with_backoff_async(
            status_err,
            max_retries=2,
            base_delay=0.01,
            retryable=DEFAULT_RETRYABLE + (httpx.HTTPStatusError,),
        )
    assert calls["n"] == 2