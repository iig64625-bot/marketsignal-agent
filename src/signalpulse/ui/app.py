"""SignalPulse Agent - Streamlit UI (v3: onboarding + dark CSS + 8 tabs)."""
from __future__ import annotations

import streamlit as st

from signalpulse.ui.i18n import t, render_lang_toggle
from signalpulse.ui.components.comparison import render_comparison
from signalpulse.ui.components.competitor_overview import render_competitor_overview
from signalpulse.ui.components.dashboard import render_dashboard
from signalpulse.ui.components.notification_config import render_notification_config
from signalpulse.ui.components.report_viewer import render_report_viewer, render_signal_timeline
from signalpulse.ui.components.run_monitor import render_run_monitor
from signalpulse.ui.components.scheduling import render_scheduling
from signalpulse.ui.components.settings import render_settings
from signalpulse.ui.components.share import render_share_panel
from signalpulse.ui.components.sidebar import render_sidebar


st.set_page_config(
    page_title="SignalPulse Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Dark-mode CSS (makes Markdown reports and pre blocks readable on dark bg) ---
st.markdown(
    """
<style>
  /* Force readable report blocks in dark mode */
  .stMarkdown .reportview-container .markdown-text-container,
  div[data-testid="stMarkdownContainer"] {
    background-color: transparent !important;
  }
  div[data-testid="stMarkdownContainer"] pre,
  div[data-testid="stMarkdownContainer"] code {
    background-color: #1e1e1e !important;
    color: #e0e0e0 !important;
    border: 1px solid #333;
  }
  div[data-testid="stMarkdownContainer"] table {
    color: inherit;
  }
  /* Make tab labels a bit bigger */
  button[role="tab"] { font-size: 15px; padding: 8px 14px; }
  /* Onboarding card */
  .onb-card {
    border: 1px solid #4f46e5;
    border-radius: 12px;
    padding: 18px 22px;
    background: linear-gradient(135deg, #1a1d2e 0%, #0e1117 100%);
    margin-bottom: 12px;
  }
  .onb-card h3 { color: #818cf8; margin: 0 0 6px 0; }
  .onb-card p  { color: #d1d5db; margin: 4px 0; }
  .onb-card code { background:#0b0b0b; color:#fbbf24; padding:1px 6px; border-radius:4px;}
  /* Metric cards in dark mode */
  [data-testid="stMetric"] {
    background: #1a1d23;
    border: 1px solid #2a2d33;
    border-radius: 10px;
    padding: 10px 14px;
  }
  /* Hide Streamlit branding */
  #MainMenu { visibility: hidden; }
  footer { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)

# --- Sidebar (must be called early so session_state can be touched) ---
render_sidebar()
render_lang_toggle()

# --- Onboarding banner: only show when no runs at all ---
def _has_runs() -> bool:
    try:
        from sqlalchemy import select
        from signalpulse.db.session import get_session
        from signalpulse.models import CrawlRun
        with get_session() as s:
            return s.execute(select(CrawlRun).limit(1)).first() is not None
    except Exception:  # noqa: BLE001
        return False


if not _has_runs() and not st.session_state.get("onboarding_dismissed", False):
    st.markdown(
        f"""
<div class="onb-card">
  <h3>{t('onboarding_title')}</h3>
  <p>{t('onboarding_caption')}</p>
  <p>{t('onboarding_step1')}</p>
  <p>{t('onboarding_step2')}</p>
  <p>{t('onboarding_step3')}</p>
</div>
""",
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([1, 1, 4])
    with c1:
        if st.button(t("onboarding_cta_sample"), type="primary", key="onb_sample"):
            st.session_state["trigger_sample_run"] = True
            st.rerun()
    with c2:
        if st.button(t("onboarding_cta_real"), key="onb_real"):
            st.session_state["trigger_real_run"] = True
            st.session_state["onboarding_dismissed"] = True
            st.rerun()
    with c3:
        if st.button(t("onboarding_skip"), key="onb_dismiss"):
            st.session_state["onboarding_dismissed"] = True
            st.rerun()

st.title(t("app_title"))
st.caption(t("app_caption"))

(
    tab_dash, tab_overview, tab_weekly, tab_battle, tab_compare,
    tab_evals, tab_runs, tab_sched, tab_settings,
) = st.tabs([
    t("dashboard"), t("competitor_overview"),
    t("weekly_report"), t("battlecards"), t("compare_runs"),
    t("eval_metrics"), t("run_history"),
    t("scheduling"), t("settings"),
])

with tab_dash:
    render_dashboard()

with tab_overview:
    render_competitor_overview()

with tab_weekly:
    render_report_viewer(report_type="weekly")
    render_share_panel(report_type="weekly")

with tab_battle:
    render_report_viewer(report_type="battlecard")
    render_share_panel(report_type="battlecard")

with tab_compare:
    render_comparison()

with tab_evals:
    st.subheader(t("eval_metrics"))
    last = st.session_state.get("last_result") or {}
    metrics = last.get("metrics") or {}
    if metrics:
        cols = st.columns(min(4, len(metrics)))
        for col, (k, v) in zip(cols, metrics.items(), strict=False):
            if isinstance(v, (int, float)):
                col.metric(k, f"{v:.2%}" if k.endswith("rate") else f"{v:.2f}")
            else:
                col.metric(k, str(v))
    else:
        st.info(t("eval_no_metrics"))
    render_signal_timeline()

with tab_runs:
    render_run_monitor()

with tab_sched:
    render_scheduling()

with tab_settings:
    render_settings()
    st.divider()
    render_notification_config()


__all__ = []