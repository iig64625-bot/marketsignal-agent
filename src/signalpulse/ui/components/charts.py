"""Plotly charts used inside the Streamlit UI.

Each renderer accepts an optional ``key`` so callers can keep element IDs
stable across re-renders. When the caller does not pass one, a uuid-based
key is generated automatically to avoid StreamlitDuplicateElementId.

The module degrades gracefully when ``plotly`` is not installed: it
falls back to the native ``st.line_chart`` / ``st.bar_chart`` / table
renderers instead of crashing the whole app.
"""
from __future__ import annotations

import uuid
from typing import Iterable

import pandas as pd
import streamlit as st

try:
    import plotly.express as px  # type: ignore
    import plotly.graph_objects as go  # type: ignore
    HAS_PLOTLY = True
except ImportError:  # noqa: BLE001
    px = None  # type: ignore
    go = None  # type: ignore
    HAS_PLOTLY = False

from signalpulse.ui.i18n import t


# Radar chart fixed 5 dimensions (used by Battlecard).
# Keys into i18n dict; resolved at render time via t().
RADAR_CATEGORY_KEYS = [
    "radar_product_velocity",
    "radar_pricing_aggressiveness",
    "radar_ecosystem_depth",
    "radar_enterprise_readiness",
    "radar_community_momentum",
]


def _auto_key(prefix: str) -> str:
    """Return a unique-enough key for a chart element."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def render_battlecard_radar(
    competitors: dict[str, list[float]],
    *,
    key: str | None = None,
) -> None:
    """Render a radar chart comparing competitors.

    Args:
        competitors: {competitor_name: [score_for_each_category]}
                     Each score is 0-10.
        key: Stable element key for Streamlit diffing. If None, a uuid
             is used (always unique, but causes a re-render every time).
    """
    if not competitors:
        st.info(t("no_data_yet"))
        return

    cats = [t(k) for k in RADAR_CATEGORY_KEYS]

    if HAS_PLOTLY:
        fig = go.Figure()
        for name, scores in competitors.items():
            closed = list(scores) + [scores[0]] if scores else []
            closed_cats = cats + [cats[0]]
            fig.add_trace(go.Scatterpolar(
                r=closed,
                theta=closed_cats,
                fill="toself",
                name=name,
                opacity=0.55,
            ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
            title=t("chart_radar_title"),
            template="plotly_dark",
            height=420,
            margin=dict(l=20, r=20, t=50, b=20),
            showlegend=True,
        )
        st.plotly_chart(fig, width="stretch", key=key or _auto_key("radar"))
    else:
        # Fallback: table view (radar is hard to replicate natively).
        rows = []
        for name, scores in competitors.items():
            row = {"competitor": name}
            for cat, score in zip(cats, scores):
                row[cat] = score
            rows.append(row)
        df = pd.DataFrame(rows)
        st.markdown(f"**{t('chart_radar_title')}** (fallback: table view)")
        st.dataframe(df, width="stretch", key=key or _auto_key("radar-tbl"))


def render_signal_bar_chart(
    rows: Iterable[dict],
    *,
    key: str | None = None,
) -> None:
    """Grouped bar chart: signal count per competitor per type.

    Each row: {"competitor": "...", "signal_type": "...", "count": N}
    """
    df = pd.DataFrame(list(rows))
    if df.empty:
        st.info(t("no_data_yet"))
        return

    if HAS_PLOTLY:
        fig = px.bar(
            df, x="competitor", y="count", color="signal_type",
            barmode="group", title=t("chart_bar_title"),
        )
        fig.update_layout(
            template="plotly_dark", height=380,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig, width="stretch", key=key or _auto_key("bar"))
    else:
        # Pivot to wide format so native bar_chart can stack/colour by signal_type.
        try:
            pivot = df.pivot_table(
                index="competitor", columns="signal_type",
                values="count", fill_value=0,
            )
            st.bar_chart(pivot, height=380)
        except Exception:
            st.bar_chart(df, x="competitor", y="count", height=380)


def render_trend_chart(
    rows: Iterable[dict],
    *,
    key: str | None = None,
) -> None:
    """Multi-line trend: signal count over time per competitor.

    Each row: {"run_date": "...", "competitor": "...", "signal_count": N}
    """
    df = pd.DataFrame(list(rows))
    if df.empty:
        st.info(t("no_data_yet"))
        return

    if HAS_PLOTLY:
        fig = px.line(
            df, x="run_date", y="signal_count", color="competitor",
            markers=True, title=t("chart_trend_title"),
        )
        fig.update_layout(
            template="plotly_dark", height=380,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig, width="stretch", key=key or _auto_key("trend"))
    else:
        # Pivot to wide so native line_chart can colour per competitor.
        try:
            pivot = df.pivot_table(
                index="run_date", columns="competitor",
                values="signal_count", fill_value=0,
            )
            st.line_chart(pivot, height=380)
        except Exception:
            st.line_chart(df, x="run_date", y="signal_count", height=380)


__all__ = [
    "render_battlecard_radar",
    "render_signal_bar_chart",
    "render_trend_chart",
    "RADAR_CATEGORY_KEYS",
    "HAS_PLOTLY",
]