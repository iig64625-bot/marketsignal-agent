"""Node: load the curated sample dataset (used by ``--use-sample-dataset``)."""
from __future__ import annotations

import datetime as _dt

from loguru import logger

from signalpulse.agents.state import GraphState
from signalpulse.db.engine import get_engine
from signalpulse.db.session import get_session, reset_session_factory
from signalpulse.models.base import utcnow
from signalpulse.models.event import Event
from signalpulse.models.normalized_document import NormalizedDocument
from signalpulse.models.signal import Signal
from signalpulse.services.sample_loader import load_sample_dataset
from signalpulse.utils.tracing import trace_node


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
        "time_window_start": (utcnow() - _dt.timedelta(days=7)).isoformat(),
        "time_window_end": utcnow().isoformat(),
        "raw_document_ids": [],
        "normalized_document_ids": norm_ids,
        "event_ids": event_ids,
        "signal_ids": signal_ids,
        "report_ids": [],
        "warnings": [],
        "metrics": {},
        "status": "running",
    }
