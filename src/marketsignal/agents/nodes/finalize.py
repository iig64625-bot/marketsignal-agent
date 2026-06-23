"""Node: mark the crawl run as completed and emit the final status."""
from __future__ import annotations

import datetime as _dt

from marketsignal.agents.state import GraphState
from marketsignal.db.session import get_session
from marketsignal.models.crawl_run import CrawlRun
from marketsignal.utils.tracing import finish_trace, trace_node


@trace_node("finalize_node")
async def finalize_node(state: GraphState) -> GraphState:
    run_id = state.get("run_id")
    if run_id:
        with get_session() as s:
            run = s.get(CrawlRun, run_id)
            if run is not None:
                run.status = "completed"
                run.finished_at = _dt.datetime.utcnow()
        finish_trace(run_id, status="completed")
    return {"status": "completed"}
