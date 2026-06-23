"""Node: call LLM to extract structured events from each normalized document."""
from __future__ import annotations

from loguru import logger

from marketsignal.agents.state import GraphState
from marketsignal.db.session import get_session
from marketsignal.events.extractor import extract_events
from marketsignal.models.normalized_document import NormalizedDocument
from marketsignal.utils.tracing import trace_node


@trace_node("extract_events_node")
async def extract_events_node(state: GraphState) -> GraphState:
    norm_ids = state.get("normalized_document_ids", [])
    event_ids: list[str] = []
    with get_session() as s:
        docs = s.query(NormalizedDocument).filter(NormalizedDocument.id.in_(norm_ids)).all() if norm_ids else []
        for doc in docs:
            try:
                events = await extract_events(doc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("extract_events: doc={} err={}", doc.id, exc)
                continue
            for ev in events:
                s.add(ev)
                event_ids.append(ev.id)
    return {"event_ids": event_ids}
