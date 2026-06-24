"""Smoke tests for the ``/metrics/{run_id}`` endpoint."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from signalpulse.api.app import create_app
from signalpulse.utils.tracing import (
    TRACE_DIR,
    finish_trace,
    get_metrics,
    start_trace,
)


@pytest.fixture
def client(tmp_data_dir: str) -> TestClient:
    """Build a TestClient with an isolated SQLite DB and trace dir."""
    import signalpulse.models  # noqa: F401
    from signalpulse.db.engine import get_engine
    from signalpulse.db.session import reset_session_factory
    from signalpulse.models.base import Base

    reset_session_factory()
    Base.metadata.create_all(get_engine())
    return TestClient(create_app())


def test_metrics_endpoint_unknown_run_returns_404(client: TestClient) -> None:
    """``GET /metrics/{run_id}`` returns 404 if no trace exists."""
    r = client.get("/metrics/nosuchrun1234")
    assert r.status_code == 404
    assert "no trace" in r.json()["detail"].lower()


def test_metrics_endpoint_zero_filled_when_no_blob(client: TestClient) -> None:
    """A trace written before the metrics upgrade returns zero-filled metrics."""
    run_id = "oldformat0001"
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    (TRACE_DIR / f"{run_id}.json").write_text(
        json.dumps({"run_id": run_id, "started_at": "x", "finished_at": "y", "spans": []}),
        encoding="utf-8",
    )
    r = client.get(f"/metrics/{run_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == run_id
    assert body["totals"]["llm_calls"] == 0
    assert body["latency_ms"]["p50"] == 0
    assert body["per_node"] == {}


def test_metrics_endpoint_returns_full_payload(client: TestClient) -> None:
    """A trace with a metrics blob is rendered into the dashboard payload."""
    run_id = "richrun0000ab"
    start_trace(run_id)
    rm = get_metrics(run_id)
    assert rm is not None
    rm.model = "gpt-4o-mini"
    rm.record_llm_call("extract_events", 1000, 2000)
    rm.record_node_latency("extract_events", 25.0)
    rm.record_node_latency("analyze_signals", 80.0)
    finish_trace(run_id, status="completed")
    r = client.get(f"/metrics/{run_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == run_id
    assert body["model"] == "gpt-4o-mini"
    assert body["totals"]["llm_calls"] == 1
    assert body["totals"]["tokens_in"] == 1000
    assert body["totals"]["tokens_out"] == 2000
    assert body["totals"]["cost_usd"] > 0
    assert body["per_node"]["extract_events"]["n_llm_calls"] == 1
    assert body["per_node"]["extract_events"]["cost_usd"] == body["totals"]["cost_usd"]
