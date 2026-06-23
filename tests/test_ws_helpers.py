"""Unit tests for pure functions in marketsignal.api.routes.ws."""
from __future__ import annotations

from marketsignal.api.routes.ws import _resolved_status, _trace_status


def test_trace_status_reads_top_level_field() -> None:
    assert _trace_status({"status": "completed"}) == "completed"
    assert _trace_status({"status": "failed"}) == "failed"
    assert _trace_status({"status": "running"}) == "running"
    assert _trace_status({}) is None
    assert _trace_status(None) is None


def test_resolved_status_prefers_trace_for_completed_or_failed() -> None:
    """If the trace says completed/failed, the WS reports it even if DB still says running."""
    assert _resolved_status("running", "completed") == "completed"
    assert _resolved_status("running", "failed") == "failed"
    # If trace says running, we trust the DB
    assert _resolved_status("completed", "running") == "completed"
    # If trace is None, we trust the DB
    assert _resolved_status("running", None) == "running"
    assert _resolved_status("completed", None) == "completed"
    # Unknown trace values are ignored
    assert _resolved_status("running", "weird") == "running"
