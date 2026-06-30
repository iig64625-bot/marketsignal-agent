"""Report viewer: list reports + show bar/radar/trend charts + export buttons (Chinese)."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import streamlit as st
from sqlalchemy import func, select

from signalpulse.db.session import get_session
from signalpulse.models.company import Company
from signalpulse.models.report import Report
from signalpulse.models.signal import Signal
from signalpulse.ui.components.charts import (
    RADAR_CATEGORY_KEYS,
    render_battlecard_radar,
    render_signal_bar_chart,
    render_trend_chart,
)
from signalpulse.ui.i18n import t


_SIGNAL_TYPE_TO_CATEGORY = {
    "product": 0,
    "pricing": 1,
    "ecosystem": 2,
    "enterprise": 3,
    "community": 4,
}

_REPORT_TYPE_KEYS = {"weekly": "report_type_weekly", "battlecard": "report_type_battlecard"}


def _list_reports(report_type: str | None = None) -> list[Report]:
    with get_session() as s:
        q = s.query(Report).order_by(Report.created_at.desc())
        if report_type:
            q = q.filter(Report.report_type == report_type)
        return list(q.limit(50).all())


def _load_markdown(path: str | None) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _signal_bar_rows(crawl_run_id: str) -> list[dict]:
    with get_session() as s:
        rows = s.execute(
            select(Company.name, Signal.signal_type, func.count(Signal.id))
            .join(Company, Signal.company_id == Company.id)
            .where(Signal.crawl_run_id == crawl_run_id)
            .group_by(Company.name, Signal.signal_type)
        ).all()
    return [
        {"competitor": n or "?", "signal_type": t or "?", "count": int(c)}
        for n, t, c in rows
    ]


def _trend_rows(limit: int = 20) -> list[dict]:
    with get_session() as s:
        rows = s.execute(
            select(Report.created_at, Company.name, func.count(Signal.id))
            .select_from(Report)
            .join(Signal, Signal.crawl_run_id == Report.crawl_run_id)
            .join(Company, Signal.company_id == Company.id)
            .group_by(Report.created_at, Company.name)
            .order_by(Report.created_at.desc())
            .limit(limit)
        ).all()
    return [
        {
            "run_date": d.strftime("%Y-%m-%d %H:%M") if d else "?",
            "competitor": n or "?",
            "signal_count": int(c),
        }
        for d, n, c in rows
    ]


def _radar_for_run(crawl_run_id: str) -> dict[str, list[float]]:
    with get_session() as s:
        rows = s.execute(
            select(Company.name, Signal.signal_type, func.count(Signal.id))
            .join(Company, Signal.company_id == Company.id)
            .where(Signal.crawl_run_id == crawl_run_id)
            .group_by(Company.name, Signal.signal_type)
        ).all()
    by_competitor: dict[str, dict[str, int]] = {}
    for name, stype, count in rows:
        by_competitor.setdefault(name or "?", {})[stype or "?"] = int(count)
    result: dict[str, list[float]] = {}
    for name, counts in by_competitor.items():
        scores = [0.0] * len(RADAR_CATEGORY_KEYS)
        for stype, n in counts.items():
            idx = _SIGNAL_TYPE_TO_CATEGORY.get((stype or "").lower())
            if idx is not None:
                scores[idx] = min(10.0, float(n) * 2.0)
        if all(s == 0 for s in scores):
            scores = [5.0] * len(RADAR_CATEGORIES)
        result[name] = scores
    return result


def _export(report, fmt: str, run_id: str | None) -> bytes:
    out_dir = Path("data/exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    rid = getattr(report, "id", "report")[:12]
    if fmt == "pdf":
        out = out_dir / f"{rid}.pdf"
        from signalpulse.reporting.export import export_to_pdf
        export_to_pdf(report, out)
    else:
        out = out_dir / f"{rid}.xlsx"
        from signalpulse.reporting.export import export_to_excel
        export_to_excel(report, out, run_id=run_id)
    return out.read_bytes()


def render_report_viewer(report_type: str = "weekly") -> None:
    label = t(_REPORT_TYPE_KEYS.get(report_type, report_type))
    st.subheader(f"{label}")
    reports = _list_reports(report_type=report_type)
    if not reports:
        st.info(t("no_report_type").format(label=label))
        return

    label_to_id = {
        f"{r.title or r.report_type} | {r.created_at:%Y-%m-%d %H:%M}": r.id for r in reports
    }
    choice = st.selectbox(
        t("select_report"),
        options=list(label_to_id.keys()),
        key=f"rv-select-{report_type}",
    )
    if not choice:
        return
    rid = label_to_id[choice]
    selected = next((r for r in reports if r.id == rid), None)
    if not selected or not selected.markdown_path:
        st.warning(t("report_missing"))
        return
    body = _load_markdown(selected.markdown_path)
    st.markdown(body, unsafe_allow_html=False)
    st.download_button(
        t("download_markdown"),
        data=body.encode("utf-8"),
        file_name=Path(selected.markdown_path).name,
        mime="text/markdown",
        use_container_width=True,
        key=f"md-dl-{rid}",
    )

    run_id = getattr(selected, "crawl_run_id", None)
    col1, col2 = st.columns(2)
    with col1:
        if st.button(t("export_pdf"), key=f"pdf-btn-{rid}", use_container_width=True):
            try:
                pdf_bytes = _export(selected, "pdf", run_id)
                st.session_state[f"pdf_bytes_{rid}"] = pdf_bytes
            except Exception as exc:  # noqa: BLE001
                st.error(t("pdf_export_failed").format(exc=exc))
        if st.session_state.get(f"pdf_bytes_{rid}"):
            st.download_button(
                t("download_pdf"),
                data=st.session_state[f"pdf_bytes_{rid}"],
                file_name=f"{report_type}_{rid[:12]}.pdf",
                mime="application/pdf",
                key=f"pdf-dl-{rid}",
                use_container_width=True,
            )
    with col2:
        if st.button(t("export_excel"), key=f"xlsx-btn-{rid}", use_container_width=True):
            try:
                xlsx_bytes = _export(selected, "xlsx", run_id)
                st.session_state[f"xlsx_bytes_{rid}"] = xlsx_bytes
            except Exception as exc:  # noqa: BLE001
                st.error(t("xlsx_export_failed").format(exc=exc))
        if st.session_state.get(f"xlsx_bytes_{rid}"):
            st.download_button(
                t("download_xlsx"),
                data=st.session_state[f"xlsx_bytes_{rid}"],
                file_name=f"{report_type}_{rid[:12]}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"xlsx-dl-{rid}",
                use_container_width=True,
            )

    if run_id:
        st.divider()
        st.subheader(t("visualization"))
        bar_rows = _signal_bar_rows(run_id)
        if bar_rows:
            st.markdown(f"**{t('by_competitor_type')}**")
            render_signal_bar_chart(bar_rows, key=f"bar-{report_type}-{run_id}")
        else:
            st.info(t("no_viz_data"))
        radar_data = _radar_for_run(run_id)
        if radar_data:
            st.markdown(f"**{t('competitor_radar')}**")
            render_battlecard_radar(radar_data, key=f"radar-{report_type}-{run_id}")


def render_signal_timeline(reports: Iterable[Report] = ()) -> None:
    st.subheader(t("signal_timeline"))
    items = list(reports) if reports else _list_reports()
    if not items:
        st.info(t("no_reports"))
        return
    rows = [
        {"created": r.created_at, "type": r.report_type, "title": r.title or t("no_title")}
        for r in items
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    try:
        trend = _trend_rows(limit=20)
        if trend:
            st.markdown(f"**{t('trend_20_runs')}**")
            render_trend_chart(trend, key="trend-timeline")
    except Exception as e:  # noqa: BLE001
        st.warning(t("trend_unavailable").format(exc=e))


__all__ = ["render_report_viewer", "render_signal_timeline"]