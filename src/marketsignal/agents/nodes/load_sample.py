"""Node: load the curated sample dataset (used by ``--use-sample-dataset``)."""
from __future__ import annotations

import datetime as _dt

from loguru import logger

from marketsignal.agents.state import GraphState
from marketsignal.db.engine import get_engine
from marketsignal.db.session import get_session, reset_session_factory
from marketsignal.models.event import Event
from marketsignal.models.normalized_document import NormalizedDocument
from marketsignal.models.signal import Signal
from marketsignal.services.sample_loader import load_sample_dataset
from marketsignal.utils.tracing import trace_node


@trace_node("load_sample_node")
async def load_sample_node(state: GraphState) -> GraphState:
    run_id = load_sample_dataset(target_name=state.get("target_company", "Dify"))
    # The sample loader commits inside its own session; dispose the engine and
    # session factory so the next query in this node gets a fresh connection.
    get_engine().dispose()
    reset_session_factory()
    with get_session() as s:
        signal_ids = [row.id for row in s.query(Signal).filter(Signal.crawl_run_id == run_id).all()]
        event_ids = [row.id for row in s.query(Event).all()]
        norm_ids = [row.id for row in s.query(NormalizedDocument).all()]
    logger.info(
        "sample dataset: run_id={} signals={} events={} docs={}",
        run_id, len(signal_ids), len(event_ids), len(norm_ids),
    )
    return {
        "run_id": run_id,
        "target_company": state.get("target_company", "Dify"),
        "competitor_ids": [],
        "source_ids": [],
        "time_window_start": (_dt.datetime.utcnow() - _dt.timedelta(days=7)).isoformat(),
        "time_window_end": _dt.datetime.utcnow().isoformat(),
        "raw_document_ids": [],
        "normalized_document_ids": norm_ids,
        "event_ids": event_ids,
        "signal_ids": signal_ids,
        "report_ids": [],
        "warnings": [],
        "metrics": {},
        "status": "running",
    }
