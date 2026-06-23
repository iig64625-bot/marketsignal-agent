"""Report viewer component: list and display generated Markdown reports."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import streamlit as st

from marketsignal.db.session import get_session
from marketsignal.models.report import Report


def _list_reports(report_type: str | None = None) -> list[Report]:
    """Fetch the most recent reports (optional ``report_type`` filter)."""
    with get_session() as s:
        q = s.query(Report).order_by(Report.created_at.desc())
        if report_type:
            q = q.filter(Report.report_type == report_type)
        return list(q.limit(50).all())


def _load_markdown(path: str | None) -> str:
    """Read a Markdown file from disk; return empty string on failure."""
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def render_report_viewer(report_type: str = "weekly") -> None:
    """Render a viewer for a given report type (``weekly`` or ``battlecard``)."""
    st.subheader(f"Reports ({report_type})")
    reports = _list_reports(report_type=report_type)
    if not reports:
        st.info(f"No {report_type} reports yet. Run a pipeline to generate one.")
        return

    label_to_id = {
        f"{r.title or r.report_type} | {r.created_at:%Y-%m-%d %H:%M}": r.id
        for r in reports
    }
    choice = st.selectbox("Select report", options=list(label_to_id.keys()))
    if not choice:
        return
    rid = label_to_id[choice]
    selected = next((r for r in reports if r.id == rid), None)
    if not selected or not selected.markdown_path:
        st.warning("Report file missing on disk.")
        return
    body = _load_markdown(selected.markdown_path)
    st.markdown(body, unsafe_allow_html=False)
    st.download_button(
        "Download Markdown",
        data=body.encode("utf-8"),
        file_name=Path(selected.markdown_path).name,
        mime="text/markdown",
        use_container_width=True,
    )


def render_signal_timeline(reports: Iterable[Report] = ()) -> None:
    """Show a small table of recent signal counts grouped by report type."""
    st.subheader("Recent signals by report")
    items = list(reports) if reports else _list_reports()
    if not items:
        st.info("No reports yet.")
        return
    rows = [
        {
            "created": r.created_at,
            "type": r.report_type,
            "title": r.title or "(untitled)",
        }
        for r in items
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


__all__ = ["render_report_viewer", "render_signal_timeline"]
