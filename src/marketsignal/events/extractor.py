"""Structured event extraction from normalized documents."""
from __future__ import annotations

import json
from typing import Any

from loguru import logger
from pydantic import ValidationError

from marketsignal.models.base import new_id
from marketsignal.models.event import Event
from marketsignal.models.normalized_document import NormalizedDocument
from marketsignal.models.schemas import EventListOutput
from marketsignal.utils.llm import get_llm

EXTRACTOR_SYSTEM_PROMPT = """You are a competitive-intelligence analyst. From the supplied
document text, extract every concrete event (product update, pricing change, hiring change,
GitHub release, user feedback, partnership, announcement). For each event return:
- event_type (one of: product_update, github_release, pricing_change, hiring_change, user_feedback, partnership, announcement)
- title (one line)
- summary (1-2 sentence factual description)
- published_at (ISO8601 if known, else null)
- confidence (0.0-1.0)
- evidence_spans (verbatim source phrases that support the event)

If no events are present, return an empty list. Do not fabricate information. Always respond
with JSON matching the requested schema."""


def _build_user_prompt(doc: NormalizedDocument) -> str:
    snippet = doc.clean_text[:6000]
    return (
        f"SOURCE TYPE: {doc.source_type}\n"
        f"TITLE: {doc.title}\n"
        f"URL: {doc.canonical_url or ''}\n"
        f"PUBLISHED AT: {doc.published_at.isoformat() if doc.published_at else 'unknown'}\n\n"
        f"--- DOCUMENT ---\n{snippet}\n--- END ---\n"
        "Return the JSON list of events."
    )


def _parse_json(content: str) -> dict[str, Any]:
    """Tolerate code-fenced JSON from LLMs that wrap their output in ```json ... ```."""
    s = content.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
    return json.loads(s)


async def extract_events(doc: NormalizedDocument) -> list[Event]:
    """Call the LLM to extract structured events from a single document.

    Returns an empty list if extraction fails or the document has no events.
    """
    if not doc.clean_text or len(doc.clean_text.strip()) < 20:
        return []
    try:
        llm = get_llm()
    except ValueError as exc:
        logger.warning("LLM not configured, skipping event extraction: {}", exc)
        return []
    structured = llm.with_structured_output(EventListOutput)
    try:
        result: EventListOutput = await structured.ainvoke(
            [
                {"role": "system", "content": EXTRACTOR_SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(doc)},
            ]
        )
    except (ValidationError, ValueError, TypeError) as exc:
        logger.warning("LLM returned invalid output: {}", exc)
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM call failed: {}", exc)
        return []
    out: list[Event] = []
    for ev in result.events:
        out.append(
            Event(
                id=new_id(),
                document_id=doc.id,
                company_id=doc.company_id,
                event_type=ev.event_type or "announcement",
                title=ev.title[:512],
                summary=ev.summary or "",
                published_at=doc.published_at,
                confidence=float(ev.confidence or 0.8),
                evidence_json=json.dumps(ev.evidence_spans or [], ensure_ascii=False),
            )
        )
    return out
