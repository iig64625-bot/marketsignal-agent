"""Node: render a weekly report from signals and persist it as a Report row."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from signalpulse.agents.state import GraphState
from signalpulse.db.session import get_session
from signalpulse.models.base import new_id
from signalpulse.models.company import Company
from signalpulse.models.report import Report
from signalpulse.models.signal import Signal
from signalpulse.reporting.render_markdown import render_weekly_report
from signalpulse.utils.tracing import trace_node


@trace_node("generate_weekly_report_node")
async def generate_weekly_report_node(state: GraphState) -> GraphState:
    run_id = state["run_id"]
    target = state.get("target_company", "target")
    signal_ids = state.get("signal_ids", [])
    report_ids: list[str] = []
    warnings = list(state.get("warnings", []))
    with get_session() as s:
        signals = s.query(Signal).filter(Signal.id.in_(signal_ids)).all() if signal_ids else []
        company_ids = {sig.company_id for sig in signals}
        name_lookup: dict[str, str] = {}
        if company_ids:
            for comp in s.query(Company).filter(Company.id.in_(company_ids)).all():
                name_lookup[comp.id] = comp.name
        try:
            markdown = render_weekly_report(
                signals,
                target_company=target,
                company_name_lookup=name_lookup,
            )
        except (ValidationError, ValueError) as exc:
            warnings.append(f"weekly render failed: {exc}")
            markdown = f"# Weekly Report\n\n_(render error: {exc})_"
        out_dir = Path(os.environ.get("SIGNALPULSE_REPORT_DIR", "data/reports"))
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"weekly_{run_id}.md"
        path.write_text(markdown, encoding="utf-8")
        report = Report(
            id=new_id(),
            crawl_run_id=run_id,
            report_type="weekly",
            company_id=None,
            title=f"Weekly Report {datetime.now(timezone.utc).date().isoformat()}",
            markdown_path=str(path),
            json_path=None,
        )
        s.add(report)
        s.flush()
        report_ids.append(report.id)
    return {"report_ids": report_ids, "warnings": warnings}
