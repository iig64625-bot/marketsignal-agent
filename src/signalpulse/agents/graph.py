"""LangGraph pipeline assembly."""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from signalpulse.agents.nodes.analyze_signals import analyze_signals_node
from signalpulse.agents.nodes.check_citations import check_citations_node
from signalpulse.agents.nodes.collect_sources import collect_sources_node
from signalpulse.agents.nodes.extract_events import extract_events_node
from signalpulse.agents.nodes.finalize import finalize_node
from signalpulse.agents.nodes.generate_battlecards import generate_battlecards_node
from signalpulse.agents.nodes.generate_weekly_report import generate_weekly_report_node
from signalpulse.agents.nodes.index_documents import index_documents_node
from signalpulse.agents.nodes.load_config import load_config_node
from signalpulse.agents.nodes.normalize_documents import normalize_documents_node
from signalpulse.agents.nodes.run_evals import run_evals_node
from signalpulse.agents.state import GraphState


def _build_full_graph() -> StateGraph:
    g = StateGraph(GraphState)
    g.add_node("load_config", load_config_node)
    g.add_node("collect_sources", collect_sources_node)
    g.add_node("normalize_documents", normalize_documents_node)
    g.add_node("extract_events", extract_events_node)
    g.add_node("index_documents", index_documents_node)
    g.add_node("analyze_signals", analyze_signals_node)
    g.add_node("generate_weekly_report", generate_weekly_report_node)
    g.add_node("generate_battlecards", generate_battlecards_node)
    g.add_node("check_citations", check_citations_node)
    g.add_node("run_evals", run_evals_node)
    g.add_node("finalize", finalize_node)
    g.set_entry_point("load_config")
    for src, dst in [
        ("load_config", "collect_sources"),
        ("collect_sources", "normalize_documents"),
        ("normalize_documents", "extract_events"),
        ("extract_events", "index_documents"),
        ("index_documents", "analyze_signals"),
        ("analyze_signals", "generate_weekly_report"),
        ("generate_weekly_report", "generate_battlecards"),
        ("generate_battlecards", "check_citations"),
        ("check_citations", "run_evals"),
        ("run_evals", "finalize"),
    ]:
        g.add_edge(src, dst)
    g.add_edge("finalize", END)
    return g


def _build_sample_graph() -> StateGraph:
    """Sample-data graph that skips fetch / LLM steps.

    Assumes ``load_sample`` has pre-populated events + signals.
    """
    from signalpulse.agents.nodes.load_sample import load_sample_node

    g = StateGraph(GraphState)
    g.add_node("load_sample", load_sample_node)
    g.add_node("generate_weekly_report", generate_weekly_report_node)
    g.add_node("generate_battlecards", generate_battlecards_node)
    g.add_node("check_citations", check_citations_node)
    g.add_node("run_evals", run_evals_node)
    g.add_node("finalize", finalize_node)
    g.set_entry_point("load_sample")
    for src, dst in [
        ("load_sample", "generate_weekly_report"),
        ("generate_weekly_report", "generate_battlecards"),
        ("generate_battlecards", "check_citations"),
        ("check_citations", "run_evals"),
        ("run_evals", "finalize"),
    ]:
        g.add_edge(src, dst)
    g.add_edge("finalize", END)
    return g


def build_pipeline(*, use_sample_dataset: bool = False):  # type: ignore[no-untyped-def]
    """Return a compiled LangGraph pipeline.

    When ``use_sample_dataset`` is True, the pipeline uses the curated sample
    dataset and skips all fetch / LLM nodes.
    """
    builder = _build_sample_graph if use_sample_dataset else _build_full_graph
    return builder().compile()


__all__ = ["build_pipeline"]
