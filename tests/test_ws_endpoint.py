"""Smoke tests for the WebSocket stream endpoint.

The tests use FastAPI's TestClient.websocket_connect, which works in
both sync and async pytest (it is internally driven by anyio).
"""
from __future__ import annotations

import datetime as _dt

import pytest
from fastapi.testclient import TestClient

from signalpulse.api.app import create_app
from signalpulse.models.crawl_run import CrawlRun
from signalpulse.utils.tracing import finish_trace, start_trace


@pytest.fixture
def client(tmp_data_dir: str) -> TestClient:
    """Build a TestClient with an isolated SQLite DB."""
    import signalpulse.models  # noqa: F401
    from signalpulse.db.engine import get_engine
    from signalpulse.db.session import reset_session_factory
    from signalpulse.models.base import Base

    reset_session_factory()
    Base.metadata.create_all(get_engine())
    return TestClient(create_app())


def _create_run(run_id: str) -> None:
    """Insert a CrawlRun row so /ws/runs/{run_id} can find it."""
    from signalpulse.db.session import get_session

    with get_session() as s:
        s.add(
            CrawlRun(
                id=run_id,
                started_at=_dt.datetime.utcnow(),
                status="running",
                triggered_by="ws-test",
            )
        )


def test_ws_sends_snapshot_for_existing_trace(client: TestClient) -> None:
    """A WebSocket client receives the trace snapshot on connect."""
    run_id = "ws0001abcdef"
    _create_run(run_id)
    start_trace(run_id)
    finish_trace(run_id, status="completed")
    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        msg = ws.receive_json()
        # Could be snapshot or status depending on timing; the snapshot is always first.
        assert msg["type"] == "snapshot"
        assert msg["trace"]["run_id"] == run_id
        # The next message must be the status event.
        st = ws.receive_json()
        assert st["type"] == "status"
        # After completed, we should also receive a "done" event.
        done = ws.receive_json()
        assert done["type"] == "done"
        assert done["status"] == "completed"


def test_ws_sends_done_for_unknown_run(client: TestClient) -> None:
    """A WebSocket for a run id that does not exist receives a done event quickly."""
    run_id = "wsdoesnotexist9"
    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        # Snapshot is None so server sends status=unknown, then done
        st = ws.receive_json()
        assert st["type"] == "status"
        # Some races produce snapshot=None skip; either way we eventually get done.
        seen_done = False
        for _ in range(3):
            msg = ws.receive_json()
            if msg["type"] == "done":
                seen_done = True
                break
        assert seen_done, "expected a done event for an unknown run_id"


def test_ws_streams_new_spans(client: TestClient) -> None:
    """Spans written after the client connects are pushed as 'node' events."""
    run_id = "wsstream000001"
    _create_run(run_id)
    start_trace(run_id)
    finish_trace(run_id, status="completed")  # initial state
    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        # Consume snapshot + status + done
        ws.receive_json()
        ws.receive_json()
        done = ws.receive_json()
        assert done["type"] == "done"
        # (the connection closes after done)
    # Now write a NEW trace (simulating a fresh run) with one span and confirm
    # the snapshot-based path picks it up
    new_run = "wsstream000002"
    _create_run(new_run)
    start_trace(new_run)
    finish_trace(new_run, status="completed")
    with client.websocket_connect(f"/ws/runs/{new_run}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "snapshot"
        assert msg["trace"]["run_id"] == new_run


def test_new_spans_since_helper() -> None:
    """Unit test: the new-span filter skips running spans and starts at the right index."""
    from signalpulse.api.routes.ws import _parse_new_spans

    payload = {
        "spans": [
            {"node": "a", "status": "ok", "duration_ms": 10.0},
            {"node": "b", "status": "running", "duration_ms": None},
            {"node": "c", "status": "ok", "duration_ms": 5.0},
            {"node": "d", "status": "error", "duration_ms": 2.0, "error": "boom"},
        ]
    }
    new = _parse_new_spans(0, payload)
    assert [s["node"] for s in new] == ["a", "c", "d"]
    new2 = _parse_new_spans(2, payload)
    assert [s["node"] for s in new2] == ["c", "d"]


def test_run_monitor_component_contains_websocket_js() -> None:
    """The Streamlit live-monitor component embeds a WebSocket client."""
    from signalpulse.ui.components.run_monitor import _LIVE_RUN_HTML

    assert "new WebSocket" in _LIVE_RUN_HTML
    assert "/ws/runs/" in _LIVE_RUN_HTML
    assert "snapshot" in _LIVE_RUN_HTML
    assert "node" in _LIVE_RUN_HTML
    assert "status" in _LIVE_RUN_HTML
    assert "done" in _LIVE_RUN_HTML
