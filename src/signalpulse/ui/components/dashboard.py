"""Dashboard v3: 4 metric cards + eval trend + 4-way filter + activity timeline."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

try:
    import plotly.express as px  # type: ignore
    HAS_PLOTLY = True
except ImportError:  # noqa: BLE001
    px = None  # type: ignore
    HAS_PLOTLY = False
from sqlalchemy import desc, func, select

from signalpulse.db.session import get_session
from signalpulse.models import Claim, Company, CrawlRun, EvalRun, Report, Signal
from signalpulse.ui.i18n import t


# ---------------- helpers ----------------

def _recent_runs(limit: int = 8) -> list:
    with get_session() as s:
        stmt = select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(limit)
        return list(s.execute(stmt).scalars().all())


def _signals_per_run_per_company(limit: int = 8) -> pd.DataFrame:
    runs = _recent_runs(limit=limit)
    if not runs:
        return pd.DataFrame(columns=["run_date", "competitor", "signal_count"])
    rows = []
    with get_session() as s:
        for r in runs:
            label = r.started_at.strftime("%m-%d %H:%M") if r.started_at else "?"
            counts = s.execute(
                select(Company.name, func.count(Signal.id))
                .join(Signal, Signal.company_id == Company.id)
                .where(Signal.crawl_run_id == r.id)
                .group_by(Company.name)
            ).all()
            for name, n in counts:
                rows.append({"run_date": label, "competitor": name, "signal_count": int(n)})
    return pd.DataFrame(rows)


def _signal_type_distribution(limit_runs: int = 5) -> pd.DataFrame:
    recent = _recent_runs(limit=limit_runs)
    if not recent:
        return pd.DataFrame(columns=["signal_type", "count"])
    recent_ids = [r.id for r in recent]
    with get_session() as s:
        rows = s.execute(
            select(Signal.signal_type, func.count(Signal.id).label("count"))
            .where(Signal.crawl_run_id.in_(recent_ids))
            .group_by(Signal.signal_type)
        ).all()
    return pd.DataFrame([{"signal_type": t or "unknown", "count": int(c)} for t, c in rows])


def _recent_signals(limit: int = 10) -> list:
    with get_session() as s:
        stmt = (
            select(Signal, Company.name)
            .join(Company, Signal.company_id == Company.id)
            .order_by(desc(Signal.created_at))
            .limit(limit)
        )
        out = []
        for sig, comp_name in s.execute(stmt).all():
            out.append({
                "signal_type": sig.signal_type or "?",
                "finding": sig.finding or "",
                "competitor": comp_name or "?",
                "created_at": sig.created_at,
            })
        return out


def _eval_trend(limit: int = 8) -> pd.DataFrame:
    with get_session() as s:
        rows = s.execute(
            select(
                EvalRun.crawl_run_id,
                CrawlRun.started_at,
                EvalRun.citation_coverage,
                EvalRun.unsupported_claim_rate,
                EvalRun.dedup_rate,
                EvalRun.token_cost_usd,
            )
            .join(CrawlRun, CrawlRun.id == EvalRun.crawl_run_id)
            .order_by(CrawlRun.started_at.asc())
            .limit(limit)
        ).all()
    if not rows:
        return pd.DataFrame()
    out = []
    for r in rows:
        out.append({
            "run_label": r.started_at.strftime("%m-%d %H:%M") if r.started_at else "?",
            "citation_coverage": float(r.citation_coverage or 0),
            "unsupported_claim_rate": float(r.unsupported_claim_rate or 0),
            "dedup_rate": float(r.dedup_rate or 0),
            "token_cost_usd": float(r.token_cost_usd or 0),
        })
    return pd.DataFrame(out)


def _citation_coverage_avg(limit: int = 5) -> float:
    with get_session() as s:
        rows = s.execute(
            select(EvalRun.citation_coverage)
            .order_by(desc(EvalRun.created_at))
            .limit(limit)
        ).scalars().all()
    covs = [float(v) for v in rows if v is not None and v > 0]
    return sum(covs) / len(covs) if covs else 0.0


def _all_signals_filtered(search: str, since: datetime | None,
                          signal_type: str | None, company: str | None) -> pd.DataFrame:
    """Filtered signals: search + time range + signal type + company."""
    with get_session() as s:
        stmt = (
            select(Signal, Company.name, CrawlRun.started_at)
            .join(Company, Signal.company_id == Company.id)
            .join(CrawlRun, CrawlRun.id == Signal.crawl_run_id)
            .order_by(desc(Signal.created_at))
        )
        if since is not None:
            stmt = stmt.where(Signal.created_at >= since)
        if signal_type and signal_type != "__all__":
            stmt = stmt.where(Signal.signal_type == signal_type)
        if company and company != "__all__":
            stmt = stmt.where(Company.name == company)
        rows = s.execute(stmt.limit(500)).all()

    df = pd.DataFrame([
        {
            "type": sig.signal_type or "?",
            "competitor": comp_name or "?",
            "finding": (sig.finding or "")[:200],
            "analysis": (sig.analysis or "")[:300],
            "run_started": rstarted,
            "signal_time": sig.created_at,
        }
        for sig, comp_name, rstarted in rows
    ])
    if df.empty or not search:
        return df
    needle = search.lower()
    mask = (
        df["finding"].str.lower().str.contains(needle, na=False)
        | df["analysis"].str.lower().str.contains(needle, na=False)
        | df["competitor"].str.lower().str.contains(needle, na=False)
        | df["type"].str.lower().str.contains(needle, na=False)
    )
    return df[mask]


# ---------------- main render ----------------

def render_dashboard() -> None:
    st.subheader(t("dashboard"))
    st.caption(t("dashboard_caption"))

    runs = _recent_runs(limit=8)
    companies_count = 0
    week_signal_count = 0
    with get_session() as s:
        companies_count = s.execute(select(func.count(Company.id))).scalar() or 0
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        week_signal_count = s.execute(
            select(func.count(Signal.id)).where(Signal.created_at >= week_ago)
        ).scalar() or 0

    if runs:
        last = runs[0]
        last_status = last.status or "?"
        status_emoji = {"completed": "✅", "failed": "❌", "running": "⏳", "pending": "🔘"}.get(last_status, "❓")
        delta_str = ""
        if len(runs) >= 2 and runs[0].started_at and runs[1].started_at:
            delta = (runs[0].started_at - runs[1].started_at).total_seconds() / 3600
            delta_str = f"{delta:+.1f}h"
    else:
        last_status = t("no_runs")
        status_emoji = "🔘"
        delta_str = ""

    avg_cov = _citation_coverage_avg()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("recent_run"), f"{status_emoji} {last_status}", delta=delta_str or None)
    c2.metric(t("week_signals"), int(week_signal_count))
    c3.metric(t("tracked_competitors"), int(companies_count))
    c4.metric(t("citation_coverage"), f"{avg_cov:.0%}" if avg_cov else "-")

    st.divider()

    # ---------------- Eval metric trend ----------------
    st.markdown(f"#### {t('eval_trend')}")
    df_eval = _eval_trend(limit=8)
    if df_eval.empty:
        st.info(t("no_data_yet"))
    else:
        df_melt = df_eval.melt(id_vars=["run_label"],
                                value_vars=["citation_coverage", "unsupported_claim_rate", "dedup_rate"],
                                var_name="metric", value_name="value")
        if HAS_PLOTLY:
            fig = px.line(df_melt, x="run_label", y="value", color="metric", markers=True)
            fig.update_layout(template="plotly_dark", height=320, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, width="stretch",
                            key=f"eval_trend-{df_eval['run_label'].iloc[-1]}")
        else:
            st.line_chart(df_melt, x="run_label", y="value", color="metric", height=320)

    st.divider()

    # ---------------- Signal trend + distribution ----------------
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown(f"#### {t('signal_trend')}")
        df_trend = _signals_per_run_per_company(limit=8)
        if df_trend.empty:
            st.info(t("no_data_yet"))
        else:
            if HAS_PLOTLY:
                fig = px.line(df_trend, x="run_date", y="signal_count",
                              color="competitor", markers=True)
                fig.update_layout(template="plotly_dark", height=320,
                                  margin=dict(l=10, r=10, t=20, b=10))
                st.plotly_chart(fig, width="stretch", key="dash-trend")
            else:
                st.line_chart(df_trend, x="run_date", y="signal_count",
                              color="competitor", height=320)
    with col_r:
        st.markdown(f"#### {t('signal_distribution')}")
        df_type = _signal_type_distribution(limit_runs=5)
        if df_type.empty:
            st.info(t("no_data_yet"))
        else:
            if HAS_PLOTLY:
                fig = px.pie(df_type, names="signal_type", values="count", hole=0.45)
                fig.update_layout(template="plotly_dark", height=320,
                                  margin=dict(l=10, r=10, t=20, b=10))
                st.plotly_chart(fig, width="stretch", key="dash-pie")
            else:
                st.bar_chart(df_type, x="count", y="signal_type", height=320, horizontal=True)

    st.divider()

    # ---------------- Filter & search ----------------
    st.markdown(f"#### {t('filter_section')}")

    # Build filter options
    with get_session() as s:
        all_types = [r[0] for r in s.execute(
            select(Signal.signal_type).distinct()).all() if r[0]]
        all_companies = [r[0] for r in s.execute(
            select(Company.name).order_by(Company.name)).all() if r[0]]

    fc1, fc2, fc3, fc4 = st.columns([3, 2, 2, 2])
    with fc1:
        search = st.text_input(t("search_placeholder"), value="",
                               placeholder=t("search_placeholder"),
                               key="dash_search")
    with fc2:
        time_choice = st.selectbox(t("time_range"),
                                   options=["all", "7d", "30d"],
                                   format_func=lambda x: {
                                       "all": t("all_time"),
                                       "7d": t("last_7d"),
                                       "30d": t("last_30d"),
                                   }[x],
                                   index=0, key="dash_time")
    with fc3:
        type_opts = ["__all__"] + sorted(all_types)
        sel_type = st.selectbox(t("signal_type_filter"), type_opts,
                                format_func=lambda x: t("all_types") if x == "__all__" else x,
                                index=0, key="dash_type")
    with fc4:
        comp_opts = ["__all__"] + sorted(all_companies)
        sel_comp = st.selectbox(t("competitor_filter"), comp_opts,
                                format_func=lambda x: t("all_competitors") if x == "__all__" else x,
                                index=0, key="dash_comp")

    since = None
    if time_choice == "7d":
        since = datetime.now(timezone.utc) - timedelta(days=7)
    elif time_choice == "30d":
        since = datetime.now(timezone.utc) - timedelta(days=30)

    df_filt = _all_signals_filtered(search, since, sel_type, sel_comp)
    if df_filt.empty:
        st.info(t("no_match"))
    else:
        st.caption(f"{len(df_filt)} {t('signals_count')}")
        st.dataframe(
            df_filt[["type", "competitor", "finding", "signal_time"]]
            .rename(columns={"type": t("col_type"), "competitor": t("col_competitor"),
                             "finding": t("col_finding"), "signal_time": t("col_time")}),
            width="stretch", hide_index=True, height=320,
        )

    st.divider()

    # ---------------- Recent activity ----------------
    st.markdown(f"#### {t('recent_activity')}")
    recent = _recent_signals(limit=10)
    if not recent:
        st.info(t("no_data_yet"))
    else:
        for r in recent:
            ts = r["created_at"].strftime("%m-%d %H:%M") if r.get("created_at") else "?"
            st.markdown(
                f"- **{r['competitor']}** · _{r['signal_type']}_ · {ts}  \n"
                f"  {r['finding'][:160]}"
            )


__all__ = ["render_dashboard"]