"""Node: turn raw documents into normalized documents and dedupe."""
from __future__ import annotations

from loguru import logger

from marketsignal.agents.state import GraphState
from marketsignal.db.session import get_session
from marketsignal.models.normalized_document import NormalizedDocument
from marketsignal.models.raw_document import RawDocument
from marketsignal.normalization.content_extractor import extract_content
from marketsignal.normalization.deduper import deduplicate
from marketsignal.utils.tracing import trace_node


@trace_node("normalize_documents_node")
async def normalize_documents_node(state: GraphState) -> GraphState:
    raw_ids = state.get("raw_document_ids", [])
    warnings = list(state.get("warnings", []))
    norm_ids: list[str] = []
    docs: list[NormalizedDocument] = []
    with get_session() as s:
        raws = s.query(RawDocument).filter(RawDocument.id.in_(raw_ids)).all() if raw_ids else []
        for raw in raws:
            try:
                nd = extract_content(raw, company_id=_company_for_source(s, raw.source_id))
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"normalize failed for raw {raw.id}: {exc}")
                logger.warning("normalize: raw={} err={}", raw.id, exc)
                continue
            s.add(nd)
            s.flush()
            norm_ids.append(nd.id)
            docs.append(nd)
    # Dedupe is in-memory; updates dedup_group on the same session.
    deduplicate(docs)
    with get_session() as s:
        for d in docs:
            s.merge(d)
    return {"normalized_document_ids": norm_ids, "warnings": warnings}


def _company_for_source(s, source_id: str) -> str:
    from marketsignal.models.source import Source
    src = s.get(Source, source_id)
    return src.company_id if src else ""
