"""Run monitor component: show recent crawl runs and their eval metrics."""
from __future__ import annotations

import streamlit as st
from sqlalchemy import desc

from marketsignal.db.session import get_session
from marketsignal.models.crawl_run import CrawlRun
from marketsignal.models.eval_run import EvalRun


def _list_runs(limit: int = 20) -> list[CrawlRun]:
    with get_session() as s:
        return list(s.query(CrawlRun).order_by(desc(CrawlRun.started_at)).limit(limit).all())


def _latest_metrics(run_id: str) -> dict[str, float]:
    with get_session() as s:
        row = (
            s.query(EvalRun)
            .filter_by(crawl_run_id=run_id)
            .order_by(desc(EvalRun.created_at))
            .first()
        )
        if not row:
            return {}
        return {
            "citation_coverage": float(row.citation_coverage or 0.0),
            "unsupported_claim_rate": float(row.unsupported_claim_rate or 0.0),
            "dedup_rate": float(row.dedup_rate or 0.0),
        }


def render_run_monitor() -> None:
    """Render a table of recent runs with their metrics."""
    st.subheader("Run history")
    runs = _list_runs()
    if not runs:
        st.info("No runs yet. Trigger one from the sidebar.")
        return
    rows = []
    for r in runs:
        m = _latest_metrics(r.id)
        rows.append(
            {
                "id": r.id,
                "status": r.status,
                "triggered_by": r.triggered_by,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "citation_coverage": m.get("citation_coverage"),
                "unsupported_claim_rate": m.get("unsupported_claim_rate"),
                "dedup_rate": m.get("dedup_rate"),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)
    failed = [r for r in runs if r.status == "failed"]
    if failed:
        with st.expander(f"Failed runs ({len(failed)})"):
            for r in failed:
                st.error(f"{r.id} @ {r.started_at}: {r.error_message or '(no message)'}")


__all__ = ["render_run_monitor"]
