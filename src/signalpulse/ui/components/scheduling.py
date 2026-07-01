"""Scheduling v1: cron-style schedules stored in schedules.yaml."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
import streamlit as st

from signalpulse.ui.i18n import t


SCHEDULES_FILE = Path("schedules.yaml")


def _load() -> list[dict]:
    if not SCHEDULES_FILE.exists():
        return []
    try:
        return list(yaml.safe_load(SCHEDULES_FILE.read_text(encoding="utf-8")) or [])
    except Exception:  # noqa: BLE001
        return []


def _save(jobs: list[dict]) -> None:
    SCHEDULES_FILE.write_text(
        yaml.safe_dump(jobs, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _next_run(cron: str) -> str:
    try:
        from croniter import croniter  # type: ignore
        return croniter(cron, datetime.now()).get_next(datetime).strftime("%Y-%m-%d %H:%M")
    except Exception:  # noqa: BLE001
        return "-"


def render_scheduling() -> None:
    st.subheader(t("schedule_title"))
    st.caption(t("schedule_caption"))
    st.warning(t("schedule_daemon_hint"))

    _CRON_PRESETS = {
        t("cron_daily_9"): "0 9 * * *",
        t("cron_weekly_mon_9"): "0 9 * * 1",
        t("cron_monthly_1st"): "0 9 1 * *",
        t("cron_every_30min"): "*/30 * * * *",
        t("cron_custom"): "__custom__",
    }

    with st.form("schedule_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            preset_choice = st.selectbox(
                t("schedule_frequency"), options=list(_CRON_PRESETS.keys()),
                index=1,
            )
            if _CRON_PRESETS[preset_choice] == "__custom__":
                cron = st.text_input(
                    t("schedule_cron"), value="0 9 * * 1",
                    help=t("schedule_cron_help"),
                )
            else:
                cron = _CRON_PRESETS[preset_choice]
        with c2:
            use_sample = st.toggle(t("schedule_use_sample"), value=True)

        cfg_options = sorted(p.name for p in Path("configs").glob("*.yaml"))
        cfg = st.selectbox(t("schedule_target"),
                           options=cfg_options or ["competitors.ai-agent.yaml"])

        submitted = st.form_submit_button(t("schedule_save_btn"), type="primary")
        if submitted:
            jobs = _load()
            jobs.append({
                "id": f"job-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "cron": cron,
                "config": cfg,
                "use_sample": use_sample,
                "enabled": True,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "last_run": None,
            })
            _save(jobs)
            st.success(t("schedule_saved"))

    st.divider()
    st.markdown(f"#### {t('schedule_list')}")
    jobs = _load()
    if not jobs:
        st.info(t("schedule_no_tasks"))
        return

    for i, j in enumerate(jobs):
        with st.container(border=True):
            cols = st.columns([1, 3, 3, 3, 2, 1])
            cols[0].markdown(f"**{j.get('id', '?')[:18]}**")
            cols[1].markdown(f"`{j.get('cron', '?')}`")
            cols[2].markdown(f"{j.get('config', '?')}")
            last = j.get("last_run") or t("schedule_never")
            cols[3].markdown(f"{t('schedule_last_run')}: {last}  \n{t('schedule_next_run')}: {_next_run(j.get('cron', '0 9 * * 1'))}")
            enabled = cols[4].toggle(t("schedule_enable"), value=j.get("enabled", True),
                                     key=f"sched_en_{i}")
            if cols[5].button(t("schedule_delete"), key=f"sched_del_{i}"):
                jobs.pop(i)
                _save(jobs)
                st.rerun()
            if cols[4].button(t("schedule_run_now"), key=f"sched_run_{i}"):
                st.session_state["trigger_sample_run"] = True if j.get("use_sample") else False
                st.rerun()
            if enabled != j.get("enabled", True):
                jobs[i]["enabled"] = enabled
                _save(jobs)


__all__ = ["render_scheduling"]