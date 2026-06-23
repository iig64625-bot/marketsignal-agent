"""Reusable retry helpers with exponential backoff and jitter.

This module is intentionally dependency-free at runtime (it only imports
:mod:`asyncio` and :mod:`random`) so that any layer of the project can use it
without pulling in a heavy retry library.
"""
from __future__ import annotations

import asyncio
import functools
import random
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from loguru import logger

T = TypeVar("T")

# Default exceptions that the async helper will treat as transient.
DEFAULT_RETRYABLE: tuple[type[BaseException], ...] = (
    asyncio.TimeoutError,
    ConnectionError,
    OSError,
)


def _compute_delay(attempt: int, base_delay: float, max_delay: float) -> float:
    """Return the next sleep duration: ``base * 2^attempt`` capped at ``max_delay``.

    Adds full jitter (random 0..delay) so concurrent callers do not synchronize.
    """
    expo = base_delay * (2 ** max(0, attempt - 1))
    expo = min(expo, max_delay)
    return random.uniform(0.0, expo)


async def retry_with_backoff_async(
    fn: Callable[..., Awaitable[T]],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable: tuple[type[BaseException], ...] = DEFAULT_RETRYABLE,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
    **kwargs: Any,
) -> T:
    """Run an async callable with exponential backoff retries.

    Args:
        fn: An async callable to invoke.
        *args: Positional args forwarded to ``fn``.
        max_retries: Total attempts (>=1). A value of 1 means try once, no retry.
        base_delay: Initial backoff in seconds.
        max_delay: Cap for the exponential backoff.
        retryable: Exception types that trigger a retry.
        on_retry: Optional hook ``(attempt, exc, delay)`` called before sleeping.
        **kwargs: Keyword args forwarded to ``fn``.

    Returns:
        The return value of the awaited ``fn``.

    Raises:
        The last exception raised by ``fn`` if all attempts fail.
    """
    if max_retries < 1:
        raise ValueError("max_retries must be >= 1")
    last_exc: BaseException | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except retryable as exc:  # noqa: PERF203
            last_exc = exc
            if attempt >= max_retries:
                logger.warning("retry: giving up after {} attempts: {}", attempt, exc)
                raise
            delay = _compute_delay(attempt, base_delay, max_delay)
            logger.warning(
                "retry: attempt {}/{} failed: {} — sleeping {:.2f}s before next try",
                attempt,
                max_retries,
                exc,
                delay,
            )
            if on_retry is not None:
                try:
                    on_retry(attempt, exc, delay)
                except Exception:  # noqa: BLE001
                    logger.exception("on_retry hook raised; continuing")
            await asyncio.sleep(delay)
    # Unreachable: the loop either returns or re-raises, but be explicit.
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("retry_with_backoff_async: exhausted without exception (logic error)")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable: tuple[type[BaseException], ...] = DEFAULT_RETRYABLE,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator variant of :func:`retry_with_backoff_async` for async callables.

    Usage::

        @retry_with_backoff(max_retries=4, base_delay=0.5)
        async def fetch(url: str) -> bytes: ...
    """

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await retry_with_backoff_async(
                fn,
                *args,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                retryable=retryable,
                **kwargs,
            )

        return wrapper

    return decorator


__all__ = [
    "DEFAULT_RETRYABLE",
    "retry_with_backoff",
    "retry_with_backoff_async",
]
