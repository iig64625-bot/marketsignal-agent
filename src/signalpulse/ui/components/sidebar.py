"""Sidebar v9: 中文 help, onboarding auto-run, anim_thread rename."""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import streamlit as st

from signalpulse.agents.graph import build_pipeline
from signalpulse.agents.state import GraphState
from signalpulse.config.loader import load_pipeline_config
from signalpulse.ui.i18n import t


_PIPELINE_STEP_KEYS = [
    ("fetch",     "pipeline_step_fetch"),
    ("normalize", "pipeline_step_normalize"),
    ("extract",   "pipeline_step_extract"),
    ("verify",    "pipeline_step_verify"),
    ("report",    "pipeline_step_report"),
    ("eval",      "pipeline_step_eval"),
]


def _friendly_error(exc: Exception) -> str:
    msg = str(exc) or ""
    low = msg.lower()
    if "401" in msg or "invalid_api_key" in low or "incorrect api key" in low:
        return t("error_api_key")
    if "connection refused" in low or "timed out" in low or "getaddrinfo" in low:
        return t("error_network")
    if "no module" in low and ("embedding" in low or "fastembed" in low):
        return t("error_embedding")
    if "rate limit" in low or "429" in msg:
        return t("error_rate_limit")
    if "model_not_found" in low or "no available channel" in low or "404" in msg:
        return t("error_model_not_found")
    return t("error_generic").format(msg=msg[:300])


def _list_config_files() -> list[Path]:
    cfg_dir = Path("configs")
    if not cfg_dir.exists():
        return []
    return sorted(p for p in cfg_dir.glob("*.yaml"))


def _run_pipeline_block(target_name: str, use_sample: bool) -> dict[str, object]:
    """Run the pipeline and return the result dict. Animates the progress bar."""
    progress = st.progress(0.0, text=t("pipeline_starting"))
    stop_anim = threading.Event()

    def _animate() -> None:
        steps = _PIPELINE_STEP_KEYS[:-1]
        for i, (_, label_key) in enumerate(steps):
            if stop_anim.wait(2.0):
                return
            pct = (i + 1) / (len(steps) + 1)
            try:
                progress.progress(pct, text=f"[{i+1}/{len(steps)}] {t(label_key)}...")
            except Exception:  # noqa: BLE001
                return

    anim_thread = threading.Thread(target=_animate, daemon=True)
    anim_thread.start()

    result: dict[str, object] = {
        "status": "failed",
        "warnings": ["config load failed"],
        "metrics": {},
    }
    try:
        pipeline = build_pipeline(use_sample_dataset=use_sample)
        initial: GraphState = {
            "target_company": target_name,
            "warnings": [],
            "metrics": {},
            "status": "pending",
        }
        result = asyncio.run(pipeline.ainvoke(initial))
        stop_anim.set()
        progress.progress(1.0, text=t("pipeline_completed"))
    except Exception as exc:  # noqa: BLE001
        stop_anim.set()
        progress.empty()
        st.error(_friendly_error(exc))
        result = {"status": "failed", "warnings": [str(exc)], "metrics": {}}
    return result


def render_sidebar() -> dict[str, object]:
    with st.sidebar:
        st.title(t("sidebar_title"))
        st.caption(t("sidebar_caption"))

        st.subheader(t("sidebar_run"))
        cfg_files = _list_config_files()
        cfg_labels = [str(p) for p in cfg_files] or ["configs/competitors.ai-agent.yaml"]
        cfg_choice = st.selectbox(
            t("sidebar_competitor_config"),
            options=cfg_labels,
            index=0,
            help=t("config_help"),
        )

        use_sample = st.toggle(
            t("sidebar_use_sample"),
            value=True,
            help=t("sample_help"),
        )

        # Auto-run from onboarding CTA
        auto_sample = st.session_state.pop("trigger_sample_run", False)
        auto_real = st.session_state.pop("trigger_real_run", False)
        if auto_sample:
            use_sample = True
        if auto_real:
            use_sample = False

        run_clicked = st.button(
            t("sidebar_run_btn"), type="primary", width="stretch",
            help=t("run_help"),
        ) or auto_sample or auto_real

        if run_clicked:
            target_name = "target"
            try:
                cfg = load_pipeline_config(cfg_choice)
                target_name = cfg.target.name
            except Exception as exc:  # noqa: BLE001
                st.error(_friendly_error(exc))
                return {"config_path": cfg_choice, "use_sample_dataset": use_sample, "run_clicked": False}

            result = _run_pipeline_block(target_name, use_sample)
            st.session_state["last_result"] = result
            st.session_state["onboarding_dismissed"] = True
            status = str(result.get("status", "?"))
            if status == "completed":
                st.success(t("analysis_completed").format(status=status))
            else:
                st.warning(t("analysis_exited").format(status=status))
            if result.get("warnings"):
                with st.expander(f"{t('warnings_count')} ({len(result['warnings'])})"):
                    for w in result["warnings"]:
                        st.warning(str(w))
            st.rerun()

        # Competitor management (lazy import to avoid circular dep)
        with st.expander(t("sidebar_competitor_mgr"), expanded=False):
            try:
                from signalpulse.ui.components.competitor_manager import render_competitor_manager
                render_competitor_manager(cfg_choice)
            except Exception as exc:  # noqa: BLE001
                st.warning(t("competitor_mgr_unavailable").format(exc=exc))

        st.divider()
        st.caption(t("sidebar_version"))
    return {
        "config_path": cfg_choice,
        "use_sample_dataset": use_sample,
        "run_clicked": run_clicked,
    }


__all__ = ["render_sidebar"]