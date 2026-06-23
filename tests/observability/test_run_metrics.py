"""Tests for the cost + latency observability layer.

Covers the in-memory :class:`RunMetrics` and the on-disk trace
serialisation round-trip. End-to-end coverage (real LLM call -> token
usage) is in :mod:`tests.test_chaos.test_extract_events_survives_bad_json`
and friends; here we focus on the deterministic arithmetic.
"""
from __future__ import annotations

import json

from marketsignal.observability.run_metrics import RunMetrics
from marketsignal.utils.tracing import (
    TRACE_DIR,
    finish_trace,
    load_trace,
    start_trace,
)


def test_run_metrics_starts_empty() -> None:
    """A fresh RunMetrics has zero tokens, calls, and latency."""
    rm = RunMetrics(run_id="r1")
    assert rm.total_tokens_in == 0
    assert rm.total_tokens_out == 0
    assert rm.total_n_calls == 0
    assert rm.total_cost_usd() == 0.0
    assert rm.latency_stats() == {"p50": 0.0, "p95": 0.0, "max": 0.0, "n": 0.0}
    assert rm.summary()["totals"] == {
        "llm_calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
    }


def test_record_llm_call_accumulates_per_node() -> None:
    """Each node's tokens add up independently across multiple calls."""
    rm = RunMetrics(run_id="r1")
    rm.record_llm_call("extract_events", tokens_in=100, tokens_out=50)
    rm.record_llm_call("extract_events", tokens_in=200, tokens_out=80)
    rm.record_llm_call("analyze_signals", tokens_in=500, tokens_out=120)
    assert rm.total_tokens_in == 800
    assert rm.total_tokens_out == 250
    assert rm.total_n_calls == 3
    assert rm.nodes["extract_events"].n_llm_calls == 2
    assert rm.nodes["analyze_signals"].n_llm_calls == 1


def test_record_node_latency_independent_of_llm_calls() -> None:
    """Latency is tracked even on nodes that do not call the LLM."""
    rm = RunMetrics(run_id="r1")
    rm.record_node_latency("load_config", 12.0)
    rm.record_node_latency("generate_weekly_report_node", 8.5)
    rm.record_llm_call("extract_events", 100, 50)
    rm.record_node_latency("extract_events", 30.0)
    stats = rm.latency_stats()
    assert stats["n"] == 3.0
    assert stats["max"] == 30.0


def test_total_cost_uses_price_table() -> None:
    """A known model uses its known price; unknown model falls back to default."""
    rm = RunMetrics(run_id="r1", model="gpt-4o-mini")
    rm.record_llm_call("x", tokens_in=1000, tokens_out=1000)
    # 1k input * 0.00015 + 1k output * 0.0006 = 0.00075
    assert abs(rm.total_cost_usd() - 0.00075) < 1e-9


def test_total_cost_zero_when_model_unknown() -> None:
    """An empty model name returns 0 cost (we cannot price it)."""
    rm = RunMetrics(run_id="r1")
    rm.record_llm_call("x", tokens_in=1000, tokens_out=1000)
    assert rm.total_cost_usd() == 0.0


def test_per_node_cost_breaks_down_each_node() -> None:
    """per_node_cost returns one USD value per node, summed equals total."""
    rm = RunMetrics(run_id="r1", model="gpt-4o-mini")
    rm.record_llm_call("a", 1000, 1000)
    rm.record_llm_call("b", 2000, 0)
    breakdown = rm.per_node_cost()
    assert set(breakdown.keys()) == {"a", "b"}
    assert abs(sum(breakdown.values()) - rm.total_cost_usd()) < 1e-9


def test_summary_serializes_to_json() -> None:
    """summary() returns plain dicts and lists (JSON-friendly)."""
    rm = RunMetrics(run_id="r1", model="gpt-4o-mini")
    rm.record_llm_call("a", 100, 50)
    rm.record_node_latency("a", 12.0)
    s = rm.summary()
    # Must round-trip through json.dumps without error
    payload = json.dumps(s, default=str)
    assert json.loads(payload)["run_id"] == "r1"


def test_to_dict_from_dict_round_trip() -> None:
    """RunMetrics.to_dict -> RunMetrics.from_dict preserves all fields."""
    rm = RunMetrics(run_id="r1", model="gpt-4o")
    rm.record_llm_call("extract_events", 100, 50)
    rm.record_llm_call("analyze_signals", 200, 80)
    rm.record_node_latency("extract_events", 12.0)
    rm.started_at = "2026-06-23T00:00:00Z"
    rm.finished_at = "2026-06-23T00:00:30Z"
    blob = rm.to_dict()
    rm2 = RunMetrics.from_dict(blob)
    assert rm2.run_id == "r1"
    assert rm2.model == "gpt-4o"
    assert rm2.total_tokens_in == 300
    assert rm2.total_tokens_out == 130
    assert rm2.total_n_calls == 2
    assert rm2.started_at == "2026-06-23T00:00:00Z"
    assert rm2.nodes["extract_events"].duration_ms == 12.0


def test_trace_writes_metrics_blob(tmp_data_dir) -> None:
    """finish_trace persists the RunMetrics blob into data/traces/{run_id}.json."""
    run_id = "abcd1234abcd"
    trace = start_trace(run_id)
    rm_payload = trace  # noqa: F841 (just to keep variable)
    # Record something via the same registry tracing uses
    from marketsignal.utils.tracing import get_metrics

    rm = get_metrics(run_id)
    assert rm is not None
    rm.record_llm_call("extract_events", 100, 50)
    rm.record_node_latency("extract_events", 25.0)
    rm.model = "gpt-4o-mini"
    finish_trace(run_id, status="completed")
    out = TRACE_DIR / f"{run_id}.json"
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "metrics" in payload
    assert payload["metrics"]["model"] == "gpt-4o-mini"
    assert payload["metrics"]["nodes"]["extract_events"]["n_llm_calls"] == 1
    assert payload["metrics"]["nodes"]["extract_events"]["tokens_in"] == 100


def test_load_trace_round_trip() -> None:
    """load_trace returns the JSON dict that was written by finish_trace."""
    run_id = "ef0123456789"
    start_trace(run_id)
    finish_trace(run_id, status="completed")
    payload = load_trace(run_id)
    assert payload is not None
    assert payload["run_id"] == run_id
    assert payload["status"] == "completed"
    assert "metrics" in payload


def test_load_trace_missing_returns_none() -> None:
    """load_trace returns None for an unknown run_id (no exception)."""
    assert load_trace("doesnotexist9999") is None
