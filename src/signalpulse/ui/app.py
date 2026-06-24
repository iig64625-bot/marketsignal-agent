"""SignalPulse Agent - Streamlit demo UI.

Launch with:
    streamlit run src/signalpulse/ui/app.py
"""
from __future__ import annotations

import streamlit as st

from signalpulse.ui.components.report_viewer import render_report_viewer, render_signal_timeline
from signalpulse.ui.components.run_monitor import render_run_monitor
from signalpulse.ui.components.sidebar import render_sidebar

st.set_page_config(
    page_title="SignalPulse Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_sidebar()

st.title("SignalPulse Agent")
st.caption("AI Competitive Intelligence - weekly reports, sales battlecards, citation-backed claims.")

tab_weekly, tab_battle, tab_evals, tab_runs = st.tabs(
    ["Weekly report", "Battlecards", "Eval metrics", "Run history"]
)

with tab_weekly:
    render_report_viewer(report_type="weekly")

with tab_battle:
    render_report_viewer(report_type="battlecard")

with tab_evals:
    st.subheader("Eval metrics")
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
        st.info("No metrics yet. Run the sample pipeline from the sidebar.")
    render_signal_timeline()

with tab_runs:
    render_run_monitor()


__all__ = []
