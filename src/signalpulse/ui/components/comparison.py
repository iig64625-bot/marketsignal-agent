"""Comparison v3: labeled selectboxes, dark mode friendly."""
from __future__ import annotations

import streamlit as st

from signalpulse.reporting.diff import compute_diff, list_recent_runs
from signalpulse.ui.i18n import t


def _run_label(r) -> str:
    started = r.started_at.strftime("%Y-%m-%d %H:%M") if r.started_at else "?"
    target = getattr(r, "target_company", None) or "?"
    return f"{r.id[:12]} · {target} · {started} · {r.status}"


def render_comparison() -> None:
    st.subheader(t("week_over_week"))
    st.caption(t("week_over_week_caption"))

    runs = list_recent_runs(limit=30)
    if len(runs) < 2:
        st.info(t("need_two_runs"))
        if st.button(t("onboarding_cta_sample"), type="primary", key="cmp_need_runs"):
            st.session_state["trigger_sample_run"] = True
            st.rerun()
        return

    labels = [_run_label(r) for r in runs]
    c1, c2 = st.columns(2)
    with c1:
        a_idx = st.selectbox(
            t("run_a"),
            options=list(range(len(runs))),
            index=min(1, len(runs) - 1),
            format_func=lambda i: labels[i],
            key="cmp_a",
        )
    with c2:
        b_idx = st.selectbox(
            t("run_b"),
            options=list(range(len(runs))),
            index=0,
            format_func=lambda i: labels[i],
            key="cmp_b",
        )

    if a_idx == b_idx:
        st.warning(t("pick_different"))
        return

    if not st.button(t("compare"), type="primary"):
        return

    try:
        diff = compute_diff(runs[a_idx].id, runs[b_idx].id)
    except Exception as exc:  # noqa: BLE001
        st.error(f"{t('diff_failed')}: {exc}")
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("week_signals"), diff.signals_b, delta=f"{diff.delta_signals:+d} {t('vs_baseline')}")
    m2.metric(t("new_claims"), diff.claims_b, delta=f"{diff.delta_claims:+d} {t('vs_baseline')}")
    m3.metric(f"{t('baseline')} · {t('week_signals')}", diff.signals_a)
    m4.metric(f"{t('baseline')} · {t('new_claims')}", diff.claims_a)

    st.markdown(f"#### {t('per_competitor')}")
    all_companies = sorted(set(diff.per_company_a) | set(diff.per_company_b))
    rows = []
    for c in all_companies:
        a = diff.per_company_a.get(c, 0)
        b = diff.per_company_b.get(c, 0)
        rows.append({t("col_competitor"): c, t("baseline"): a, t("current"): b, t("col_delta"): b - a})
    st.dataframe(rows, width="stretch", hide_index=True)

    if diff.new_claims:
        st.markdown(f"#### {t('new_claims')} ({len(diff.new_claims)})")
        for c in diff.new_claims:
            st.markdown(f"- {c}")
    else:
        st.info(t("no_new_claims"))

    if diff.removed_claims:
        with st.expander(f"{t('removed_claims')} ({len(diff.removed_claims)})"):
            for c in diff.removed_claims:
                st.markdown(f"- {c}")


__all__ = ["render_comparison"]