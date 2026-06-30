"""Node: group events by company and ask the LLM for market signals."""
from __future__ import annotations

import datetime as _dt
import json
from collections import defaultdict

from loguru import logger
from pydantic import ValidationError

from signalpulse.agents.state import GraphState
from signalpulse.db.session import get_session
from signalpulse.models.base import new_id
from signalpulse.models.company import Company
from signalpulse.models.event import Event
from signalpulse.models.schemas import SignalListOutput
from signalpulse.models.signal import Signal
from signalpulse.utils.llm import get_llm
from signalpulse.utils.tracing import trace_node

ANALYZE_SYSTEM_PROMPT = """You are a market analyst. Given a set of events for one competitor,
identify market signals. For each signal return JSON with: signal_type, finding, analysis,
recommendation, confidence (high|medium|low), and supporting_event_ids. Do not invent facts not
present in the events; speculative analysis must be flagged with medium or low confidence.

IMPORTANT: Write the ''finding'' and ''analysis'' fields in **Chinese (中文)**. Keep technical product names (e.g., Coze, FastGPT, GPT, Claude, Cursor) and field keys (signal_type, confidence) in their original English."""


@trace_node("analyze_signals_node")
async def analyze_signals_node(state: GraphState) -> GraphState:
    run_id = state["run_id"]
    event_ids = state.get("event_ids", [])
    signal_ids: list[str] = []
    warnings = list(state.get("warnings", []))
    with get_session() as s:
        events = s.query(Event).filter(Event.id.in_(event_ids)).all() if event_ids else []
        groups: dict[str, list[Event]] = defaultdict(list)
        for ev in events:
            groups[ev.company_id].append(ev)
        try:
            llm = get_llm()
            structured = llm.with_structured_output(SignalListOutput)
        except ValueError as exc:
            logger.warning("analyze_signals: LLM unavailable: {}", exc)
            warnings.append(f"analyze_signals skipped: {exc}")
            return {"signal_ids": signal_ids, "warnings": warnings}
        for company_id, group in groups.items():
            company = s.get(Company, company_id)
            company_name = company.name if company else company_id
            # Sort by published_at desc (newest first), then drop the tail
            # if it would blow up the prompt budget.
            sorted_group = sorted(
                group,
                key=lambda ev: ev.published_at or _dt.datetime.min,
                reverse=True,
            )
            truncated = len(sorted_group) > MAX_EVENTS_PER_COMPETITOR
            if truncated:
                warnings.append(
                    f"analyze_signals: {company_name} has {len(sorted_group)} events, "
                    f"truncated to {MAX_EVENTS_PER_COMPETITOR} most recent"
                )
                sorted_group = sorted_group[:MAX_EVENTS_PER_COMPETITOR]
            prompt = _build_prompt(company_name, sorted_group, truncated=truncated)
            try:
                from signalpulse.observability.llm_tracking import invoke_with_metrics

                result: SignalListOutput = await invoke_with_metrics(
                    run_id=run_id,
                    node="analyze_signals_node",
                    llm=structured,
                    messages=[
                        {"role": "system", "content": ANALYZE_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                )
            except (ValidationError, ValueError, TypeError) as exc:
                warnings.append(f"signal parse failed for {company_name}: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"signal LLM call failed for {company_name}: {exc}")
                continue
            for sig in result.signals:
                row = Signal(
                    id=new_id(),
                    crawl_run_id=run_id,
                    company_id=company_id,
                    signal_type=sig.signal_type,
                    finding=sig.finding,
                    analysis=sig.analysis,
                    recommendation=sig.recommendation,
                    confidence=sig.confidence or "medium",
                    supporting_event_ids_json=json.dumps(sig.supporting_event_ids or []),
                    supporting_document_ids_json=json.dumps([]),
                )
                s.add(row)
                signal_ids.append(row.id)
    return {"signal_ids": signal_ids, "warnings": warnings}


# Per-line caps protect the prompt from a single event blowing up the
# context. We picked 100 / 300 to keep the per-event line under ~80 tokens
# while still leaving room for the event type + id.
MAX_TITLE_CHARS = 100
MAX_SUMMARY_CHARS = 300
# Hard cap on events per competitor. Above this, we keep the first N and
# drop the rest (sorted by published_at desc inside the caller).
MAX_EVENTS_PER_COMPETITOR = 50


def _build_prompt(company: str, events: list[Event], *, truncated: bool = False) -> str:
    """Build the per-competitor analysis prompt.

    Args:
        company: The competitor's display name.
        events: Events to include in the prompt.
        truncated: If True, the caller dropped some events to fit
            :data:`MAX_EVENTS_PER_COMPETITOR`. We add a one-line note so
            the LLM knows the list is incomplete.
    """
    lines = [f"COMPETITOR: {company}", f"EVENTS ({len(events)}):"]
    if truncated:
        lines.append(
            f"NOTE: showing the {len(events)} most recent events; older events were dropped to fit the prompt budget."
        )
    for e in events:
        title = (e.title or "")[:MAX_TITLE_CHARS]
        summary = (e.summary or "")[:MAX_SUMMARY_CHARS]
        lines.append(
            f"- id={e.id} type={e.event_type} title={title} summary={summary}"
        )
    lines.append("Return the JSON list of signals.")
    return "\n".join(lines)
