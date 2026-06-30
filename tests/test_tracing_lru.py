"""Tests for Task D: trace registry LRU + on-disk cleanup."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

import signalpulse.utils.tracing as tracing_mod
from signalpulse.utils.tracing import (
    _MAX_AGE_SECONDS,
    _MAX_ENTRIES,
    _drop_locked,
    _prune_locked,
    _trace_path,
    finish_trace,
    get_metrics,
    start_trace,
)


@pytest.fixture(autouse=True)
def _clean_registry(tmp_path, monkeypatch):
    """Reset the module-level dicts + TRACE_DIR for each test."""
    monkeypatch.setattr(tracing_mod, "_CURRENT", {})
    monkeypatch.setattr(tracing_mod, "_METRICS", {})
    monkeypatch.setattr(tracing_mod, "TRACE_DIR", tmp_path)
    yield


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _metrics_keys() -> set[str]:
    """Read keys from the (possibly-monkeypatched) module dict."""
    return set(tracing_mod._METRICS.keys())


def test_prune_drops_old_runs() -> None:
    """A run with finished_at older than _MAX_AGE_SECONDS is dropped."""
    start_trace("r-old")
    rm = get_metrics("r-old")
    assert rm is not None
    # Set finished_at to 25 hours ago (well past the 24h TTL)
    rm.finished_at = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() - (_MAX_AGE_SECONDS + 600),
        tz=timezone.utc,
    ).isoformat().replace("+00:00", "Z")
    _prune_locked()
    assert "r-old" not in _metrics_keys()


def test_prune_keeps_recent_runs() -> None:
    """A run with finished_at within _MAX_AGE_SECONDS stays."""
    start_trace("r-new")
    rm = get_metrics("r-new")
    rm.finished_at = _now_iso()
    _prune_locked()
    assert "r-new" in _metrics_keys()


def test_prune_caps_total_count() -> None:
    """When more than _MAX_ENTRIES runs exist, the oldest are dropped."""
    newest_id = ""
    for i in range(_MAX_ENTRIES + 10):
        rid = f"r{i:04d}"
        newest_id = rid
        start_trace(rid)
        rm = get_metrics(rid)
        rm.finished_at = _now_iso()
    _prune_locked()
    assert len(_metrics_keys()) <= _MAX_ENTRIES
    # The newest run should survive
    assert newest_id in _metrics_keys()


def test_drop_removes_disk_file() -> None:
    """_drop_locked deletes the on-disk trace JSON for the run."""
    start_trace("r-drop")
    finish_trace("r-drop", status="completed")
    p = _trace_path("r-drop")
    assert p.exists()
    _drop_locked("r-drop")
    assert not p.exists()
    assert "r-drop" not in _metrics_keys()
    assert "r-drop" not in tracing_mod._CURRENT


def test_finish_trace_prunes() -> None:
    """finish_trace() invokes prune, keeping the registry bounded."""
    for i in range(_MAX_ENTRIES + 5):
        rid = f"r-fin{i:04d}"
        start_trace(rid)
        finish_trace(rid, status="completed")
    assert len(_metrics_keys()) <= _MAX_ENTRIES


def test_prune_handles_invalid_iso_format() -> None:
    """A run with a malformed finished_at does not crash the prune loop."""
    start_trace("r-bad")
    rm = get_metrics("r-bad")
    rm.finished_at = "not-a-date"
    _prune_locked()  # must not raise
    # The bad-iso run stays (we couldn't tell it was old)
    assert "r-bad" in _metrics_keys()
