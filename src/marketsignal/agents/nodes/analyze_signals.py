"""Node: group events by company and ask the LLM for market signals."""
from __future__ import annotations

import json
from collections import defaultdict

from loguru import logger
from pydantic import ValidationError

from marketsignal.agents.state import GraphState
from marketsignal.db.session import get_session
from marketsignal.models.base import new_id
from marketsignal.models.company import Company
from marketsignal.models.event import Event
from marketsignal.models.schemas import SignalListOutput
from marketsignal.models.signal import Signal
from marketsignal.utils.llm import get_llm
from marketsignal.utils.tracing import trace_node

ANALYZE_SYSTEM_PROMPT = """You are a market analyst. Given a set of events for one competitor,
identify market signals. For each signal return JSON with: signal_type, finding, analysis,
recommendation, confidence (high|medium|low), and supporting_event_ids. Do not invent facts not
present in the events; speculative analysis must be flagged with medium or low confidence."""


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
            prompt = _build_prompt(company_name, group)
            try:
                from marketsignal.observability.llm_tracking import invoke_with_metrics

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


def _build_prompt(company: str, events: list[Event]) -> str:
    lines = [f"COMPETITOR: {company}", f"EVENTS ({len(events)}):"]
    for e in events:
        lines.append(f"- id={e.id} type={e.event_type} title={e.title} summary={e.summary}")
    lines.append("Return the JSON list of signals.")
    return "\n".join(lines)
