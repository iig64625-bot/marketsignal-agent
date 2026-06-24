"""Tests for the LangGraph pipeline structure."""

from __future__ import annotations

from signalpulse.agents.graph import build_pipeline
from signalpulse.agents.state import GraphState

EXPECTED_NODES = {
    "load_config",
    "collect_sources",
    "normalize_documents",
    "extract_events",
    "index_documents",
    "analyze_signals",
    "generate_weekly_report",
    "generate_battlecards",
    "check_citations",
    "run_evals",
    "finalize",
}


def test_build_pipeline_returns_compiled_graph():
    """``build_pipeline`` returns a graph containing the 11 expected nodes."""
    app = build_pipeline()
    assert app is not None
    # LangGraph exposes nodes via .get_graph().nodes
    node_names = set(app.get_graph().nodes.keys())
    # Subtract the special start/end nodes
    node_names -= {"__start__", "__end__"}
    assert EXPECTED_NODES.issubset(node_names), f"missing: {EXPECTED_NODES - node_names}"


def test_graph_state_typed_dict_keys():
    """The GraphState TypedDict exposes the documented keys."""
    sample: GraphState = {
        "run_id": "r1",
        "target_company": "Dify",
        "competitor_ids": ["c1"],
        "source_ids": ["s1"],
        "time_window_start": "2025-01-01T00:00:00",
        "time_window_end": "2025-01-08T00:00:00",
        "raw_document_ids": [],
        "normalized_document_ids": [],
        "event_ids": [],
        "signal_ids": [],
        "report_ids": [],
        "warnings": [],
        "metrics": {},
        "status": "pending",
    }
    assert sample["run_id"] == "r1"
    assert isinstance(sample["metrics"], dict)
