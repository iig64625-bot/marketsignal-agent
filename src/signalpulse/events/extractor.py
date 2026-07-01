"""Structured event extraction from normalized documents."""
from __future__ import annotations

import json
from typing import Any

from loguru import logger
from pydantic import ValidationError

from signalpulse.models.base import new_id
from signalpulse.models.event import Event
from signalpulse.models.normalized_document import NormalizedDocument
from signalpulse.models.schemas import EventListOutput
from signalpulse.utils.llm import get_llm

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
with a JSON object whose top-level "events" field contains the list of events (e.g. `{"events": [...]}`). The wrapper object is required."""


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


async def extract_events(
    doc: NormalizedDocument,
    *,
    run_id: str | None = None,
    node: str = "extract_events",
) -> list[Event]:
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
    # NOTE: skip with_structured_output — DeepSeek does not support
    # ``response_format: json_schema`` (returns 400 "unavailable now").
    # Use plain LLM call + manual JSON parsing via the existing _parse_json helper.
    try:
        from signalpulse.observability.llm_tracking import invoke_with_metrics

        result_msg = await invoke_with_metrics(
            run_id=run_id,
            node=node,
            llm=llm,
            messages=[
                {"role": "system", "content": EXTRACTOR_SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(doc)},
            ],
        )
        # AIMessage.content is a JSON string (system prompt asks for JSON).
        # _parse_json strips ```json ... ``` fences if the LLM adds them.
        content = getattr(result_msg, "content", None) or str(result_msg)
        data = _parse_json(content)
        # Tolerate LLMs that return a bare list instead of {"events": [...]}.
        if isinstance(data, list):
            data = {"events": data}
        result = EventListOutput.model_validate(data)
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
