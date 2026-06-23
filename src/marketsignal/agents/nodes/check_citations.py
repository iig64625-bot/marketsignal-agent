"""Node: check citations for every report in this run."""
from __future__ import annotations

from loguru import logger

from marketsignal.agents.state import GraphState
from marketsignal.citation.checker import check_report_citations, compute_citation_metrics
from marketsignal.db.session import get_session
from marketsignal.models.report import Report
from marketsignal.utils.tracing import trace_node


@trace_node("check_citations_node")
async def check_citations_node(state: GraphState) -> GraphState:
    warnings = list(state.get("warnings", []))
    report_ids = state.get("report_ids", [])
    metrics = dict(state.get("metrics", {}))
    all_claims: list = []
    with get_session() as s:
        reports = s.query(Report).filter(Report.id.in_(report_ids)).all() if report_ids else []
        for r in reports:
            try:
                claims = check_report_citations(r, s)
            except Exception as exc:  # noqa: BLE001
                logger.warning("citation check failed for report={} err={}", r.id, exc)
                warnings.append(f"citation check failed for {r.id}: {exc}")
                continue
            all_claims.extend(claims)
    if all_claims:
        m = compute_citation_metrics(all_claims)
        metrics.update(m)
    return {"metrics": metrics, "warnings": warnings}
