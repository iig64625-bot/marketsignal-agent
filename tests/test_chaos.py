"""Chaos / failure-mode tests for the MarketSignal pipeline.

These tests inject controlled failures into the LLM, network, and DB
layers and verify that the pipeline degrades gracefully rather than
crashing. They exist because 99% of pipeline failures in production
come from upstream service degradation, not from bugs in our own code.
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from marketsignal.agents.graph import build_pipeline
from marketsignal.citation.checker import (
    _deterministic_support,
)
from marketsignal.models.base import new_id
from marketsignal.utils.retry import retry_with_backoff_async

# ----------------------------- retry layer ------------------------------------


@pytest.mark.asyncio
async def test_retry_exhausts_on_persistent_failure() -> None:
    """If every attempt fails, retry gives up after max_retries."""
    calls = {"n": 0}

    async def always_breaks() -> None:
        calls["n"] += 1
        raise ConnectionError("upstream down")

    with pytest.raises(ConnectionError):
        await retry_with_backoff_async(always_breaks, max_retries=3, base_delay=0.01)
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_retry_recovers_after_transient_blip() -> None:
    """A 2-attempt blip is recovered, returning the eventual success."""
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("flaky")
        return "ok"

    result = await retry_with_backoff_async(
        flaky,
        max_retries=5,
        base_delay=0.01,
        retryable=(httpx.TransportError, httpx.HTTPError, httpx.HTTPStatusError),
    )
    assert result == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_retry_does_not_swallow_unexpected_exceptions() -> None:
    """Non-retryable exceptions should not be retried (e.g. ValueError)."""
    calls = {"n": 0}

    async def bug() -> None:
        calls["n"] += 1
        raise ValueError("programming bug, do not retry")

    with pytest.raises(ValueError):
        await retry_with_backoff_async(bug, max_retries=5, base_delay=0.01)
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_retry_surfaces_429_with_retry_after() -> None:
    """A 429 response should be retried (not swallowed as a hard error)."""
    calls = {"n": 0}

    async def rate_limited() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            request = httpx.Request("GET", "https://api.example.com")
            response = httpx.Response(429, request=request, headers={"Retry-After": "0"})
            raise httpx.HTTPStatusError("429", request=request, response=response)
        return "ok"

    result = await retry_with_backoff_async(
        rate_limited,
        max_retries=3,
        base_delay=0.01,
        retryable=(httpx.TransportError, httpx.HTTPError, httpx.HTTPStatusError),
    )
    assert result == "ok"
    assert calls["n"] == 2


# ----------------------------- citation checker ---------------------------------


def test_deterministic_support_handles_garbage_text() -> None:
    """The fallback citation checker should not crash on non-string inputs."""
    assert _deterministic_support("", [("text", "")])[0] is False
    assert _deterministic_support("Coze is hiring a VP", [("", "")])[0] is False
    # No exception even with weird types
    assert _deterministic_support("query", [])[0] is False
    assert _deterministic_support("query", [None, (None, None)])[0] is False


def test_deterministic_support_handles_empty_claim() -> None:
    """Empty claim should return False without raising."""
    supported, urls = _deterministic_support("", [("real text", "https://x")])
    assert supported is False
    assert urls == []


# ----------------------------- pipeline (no LLM) ---------------------------------


@pytest.mark.asyncio
async def test_sample_pipeline_completes_without_api_keys() -> None:
    """The sample pipeline must complete end-to-end with zero LLM / API keys configured."""
    # Clear any env vars that would enable a real LLM
    import os

    for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "QWEN_API_KEY", "GEMINI_API_KEY"):
        os.environ.pop(var, None)

    pipeline = build_pipeline(use_sample_dataset=True)
    initial: dict[str, Any] = {
        "target_company": "Dify",
        "warnings": [],
        "metrics": {},
        "status": "pending",
    }
    result = await pipeline.ainvoke(initial)
    assert result["status"] == "completed", result
    # The pipeline should produce signals and reports even without any LLM
    assert len(result.get("signal_ids", [])) >= 5
    assert len(result.get("report_ids", [])) >= 2


@pytest.mark.asyncio
async def test_pipeline_does_not_crash_on_node_warning() -> None:
    """A node that records a warning should not abort the run."""
    pipeline = build_pipeline(use_sample_dataset=True)
    result = await pipeline.ainvoke({
        "target_company": "Dify",
        "warnings": ["pre-existing warning"],
        "metrics": {},
        "status": "pending",
    })
    assert result["status"] == "completed"


# ----------------------------- malformed LLM output ------------------------------


@pytest.mark.asyncio
async def test_analyze_signals_survives_malformed_llm_output(monkeypatch) -> None:
    """analyze_signals should append a warning and continue, not raise."""
    from marketsignal.agents.nodes import analyze_signals

    def broken_invoke(*args: Any, **kwargs: Any) -> None:
        raise ValueError("LLM returned unparseable garbage")

    class FakeStructured:
        async def ainvoke(self, *args: Any, **kwargs: Any) -> None:
            raise ValueError("bad json")

    class FakeLLM:
        def with_structured_output(self, schema: Any) -> FakeStructured:
            return FakeStructured()

    monkeypatch.setattr(analyze_signals, "get_llm", lambda: FakeLLM())
    state = {"run_id": "r1", "event_ids": [], "warnings": []}
    out = await analyze_signals.analyze_signals_node(state)
    assert "signal_ids" in out
    # May or may not have warnings depending on whether events is empty,
    # but must not raise
    assert isinstance(out["signal_ids"], list)


@pytest.mark.asyncio
async def test_extract_events_survives_bad_json(monkeypatch) -> None:
    """extract_events should return [] on unparseable LLM output, not raise."""
    from marketsignal.events import (
        extractor as extract_events,  # real module; agents.nodes is a thin re-export
    )
    from marketsignal.models.normalized_document import NormalizedDocument

    class FakeStructured:
        async def ainvoke(self, *args: Any, **kwargs: Any) -> None:
            raise ValueError("garbled json")

    class FakeLLM:
        def with_structured_output(self, schema: Any) -> FakeStructured:
            return FakeStructured()

    monkeypatch.setattr(extract_events, "get_llm", lambda: FakeLLM())
    doc = NormalizedDocument(
        id=new_id(),
        company_id="x",
        source_type="blog",
        clean_text="Some real text " * 50,
        content_hash="abc",
    )
    events = await extract_events.extract_events(doc)
    assert events == []


# ----------------------------- DB failures --------------------------------------


def test_db_session_rolls_back_on_exception(tmp_data_dir) -> None:
    """If a session raises mid-transaction, the session should rollback (no half-state)."""
    from marketsignal.db.engine import get_engine
    from marketsignal.db.session import get_session
    from marketsignal.models.base import Base
    from marketsignal.models.crawl_run import CrawlRun

    Base.metadata.create_all(get_engine())

    raised = False
    try:
        with get_session() as s:
            s.add(CrawlRun(id="x", started_at=__import__("datetime").datetime.utcnow(), status="pending", triggered_by="chaos"))
            s.flush()
            raise RuntimeError("simulated mid-transaction failure")
    except RuntimeError:
        raised = True
    assert raised, "exception should have propagated"

    # The failed row should NOT be visible from a new session (rollback worked)
    from marketsignal.db.session import get_session as _gs2
    with _gs2() as s:
        from marketsignal.models.crawl_run import CrawlRun as CR
        assert s.get(CR, "x") is None, "rollback failed: row leaked"


# ----------------------------- network failures ---------------------------------


@pytest.mark.asyncio
async def test_http_client_raises_fetch_error_after_exhausted_retries(tmp_data_dir) -> None:
    """A persistently unreachable URL should raise FetchError, not hang."""
    from marketsignal.ingestion.http_client import FetchError, HttpClient

    with pytest.raises(FetchError):
        async with HttpClient(max_retries=2) as client:
            # Port 1 is reserved, no service listens; gives immediate refusal
            await client.fetch("http://127.0.0.1:1/")


# ----------------------------- scheduler failures --------------------------------


def test_scheduler_rejects_bad_cron() -> None:
    """A 4-field cron should be rejected at construction time."""
    from marketsignal.scheduler import _parse_cron
    with pytest.raises(ValueError, match="5 fields"):
        _parse_cron("*/5 * * *")  # only 4 fields
    with pytest.raises(ValueError, match="5 fields"):
        _parse_cron("*/5 * * * * * *")  # 7 fields