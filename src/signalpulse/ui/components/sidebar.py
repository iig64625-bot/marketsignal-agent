"""Sidebar component: choose config, mode, and trigger a pipeline run."""
from __future__ import annotations

import asyncio
from pathlib import Path

import streamlit as st

from signalpulse.agents.graph import build_pipeline
from signalpulse.agents.state import GraphState
from signalpulse.config.loader import load_pipeline_config


def _list_config_files() -> list[Path]:
    """Return all ``configs/*.yaml`` files in the project root."""
    cfg_dir = Path("configs")
    if not cfg_dir.exists():
        return []
    return sorted(p for p in cfg_dir.glob("*.yaml"))


def render_sidebar() -> dict[str, object]:
    """Render the sidebar and return a dict of the user selections."""
    with st.sidebar:
        st.title("SignalPulse")
        st.caption("AI Competitive Intelligence")

        st.subheader("Run")
        cfg_files = _list_config_files()
        cfg_labels = [str(p) for p in cfg_files] or ["configs/competitors.ai-agent.yaml"]
        cfg_choice = st.selectbox(
            "Competitor config",
            options=cfg_labels,
            index=0,
            help="YAML file under configs/ that defines target + competitors.",
        )

        use_sample = st.toggle(
            "Use sample dataset (offline, 0 LLM cost)",
            value=True,
            help="Run the pre-curated 9-event / 9-signal sample pipeline.",
        )

        run_clicked = st.button("Run pipeline", type="primary", use_container_width=True)
        if run_clicked:
            with st.spinner("Pipeline running..."):
                try:
                    cfg = load_pipeline_config(cfg_choice)
                    target_name = cfg.target.name
                except Exception as exc:
                    st.error(f"Failed to load config: {exc}")
                    target_name = "target"
                try:
                    pipeline = build_pipeline(use_sample_dataset=use_sample)
                    initial: GraphState = {
                        "target_company": target_name,
                        "warnings": [],
                        "metrics": {},
                        "status": "pending",
                    }
                    result = asyncio.run(pipeline.ainvoke(initial))
                except Exception as exc:
                    st.error(f"Pipeline failed: {exc}")
                    result = {"status": "failed", "warnings": [str(exc)], "metrics": {}}
                st.session_state["last_result"] = result
                st.success(f"Done: status={result.get('status', '?')}")
                if result.get("warnings"):
                    with st.expander(f"Warnings ({len(result['warnings'])})"):
                        for w in result["warnings"]:
                            st.warning(str(w))
                st.rerun()

        st.divider()
        st.caption("v0.1.0 · LangGraph · Chroma · FastAPI")
    return {
        "config_path": cfg_choice,
        "use_sample_dataset": use_sample,
        "run_clicked": run_clicked,
    }


__all__ = ["render_sidebar"]
