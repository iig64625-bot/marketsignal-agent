"""Render weekly reports and battlecards as Markdown."""
from __future__ import annotations

import datetime as _dt
from collections import Counter, defaultdict
from collections.abc import Iterable

from signalpulse.models.signal import Signal
from signalpulse.reporting.templates import BATTLECARD_SECTIONS, WEEKLY_SECTIONS


def _signal_to_dict(s: Signal) -> dict[str, object]:
    return {
        "id": s.id,
        "company_id": s.company_id,
        "signal_type": s.signal_type,
        "finding": s.finding,
        "analysis": s.analysis,
        "recommendation": s.recommendation,
        "confidence": s.confidence,
        "supporting_event_ids": s.supporting_event_ids_json or "[]",
        "supporting_document_ids": s.supporting_document_ids_json or "[]",
    }


def _render_table(rows, headers):
    if not rows:
        return "_(no rows)_\n"
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines) + "\n"


def _render_attack_points(extras):
    if not extras:
        return "_(no LLM-generated attack points; enable an LLM provider for richer cards)_\n"
    attack_points = extras.get("attack_points") or []
    talk_tracks = extras.get("talk_tracks") or []
    pitch = extras.get("sales_pitch") or ""
    summary = extras.get("summary") or ""
    out = []
    if summary:
        out.append("**TL;DR:** " + summary)
    if pitch:
        out.append("**Elevator pitch:** " + pitch)
    if attack_points:
        out.append("")
        for ap in attack_points:
            if not isinstance(ap, dict):
                continue
            weakness = ap.get("weakness", "")
            evidence = ap.get("evidence", "")
            conf = ap.get("confidence", 0.5)
            if weakness:
                line = "- " + weakness + " _(confidence: " + f"{conf:.0%}" + ")_"
                if evidence:
                    line += " - " + evidence
                out.append(line)
    if talk_tracks:
        out.append("")
        out.append("**Talk tracks:**")
        for t in talk_tracks:
            if not isinstance(t, dict):
                continue
            situation = t.get("situation", "")
            line_text = t.get("line", "")
            if line_text:
                if situation:
                    out.append("- _When:_ " + situation + " -> _Say:_ " + line_text)
                else:
                    out.append("- " + line_text)
    if not out:
        return "_(no LLM-generated attack points)_\n"
    return "\n".join(out) + "\n"


def render_weekly_report(
    signals: Iterable[Signal],
    *,
    target_company: str,
    citations=None,
    company_name_lookup=None,
) -> str:
    sigs = list(signals)
    today = _dt.date.today().isoformat()
    by_company = defaultdict(list)
    for s in sigs:
        by_company[s.company_id].append(s)
    company_names = company_name_lookup or {}

    def name(cid):
        return company_names.get(cid, cid)

    by_type = Counter(s.signal_type for s in sigs)
    type_rows = [[k, str(v)] for k, v in sorted(by_type.items(), key=lambda x: -x[1])]
    company_rows = [[name(c), str(len(g))] for c, g in sorted(by_company.items(), key=lambda x: -len(x[1]))]
    high = sum(1 for s in sigs if s.confidence == "high")
    summary_md = (
        "This week the pipeline observed **{n}** market signals across **{m}** competitors of **{t}**. Of these, **{h}** are high-confidence.\n\n"
        "### Signals by Type\n{table1}### Signals by Competitor\n{table2}"
    ).format(
        n=len(sigs), m=len(by_company), t=target_company, h=high,
        table1=_render_table(type_rows, ["signal_type", "count"]),
        table2=_render_table(company_rows, ["competitor", "count"]),
    )

    key_changes_parts = []
    for cid, group in sorted(by_company.items(), key=lambda x: -len(x[1])):
        key_changes_parts.append("### " + name(cid) + "\n")
        for s in group:
            key_changes_parts.append("- **[" + s.signal_type + "]** " + s.finding + " _(confidence: " + s.confidence + ")_\n")
            if s.analysis:
                key_changes_parts.append("  - Analysis: " + s.analysis + "\n")
        key_changes_parts.append("")

    product = [s for s in sigs if s.signal_type in {"product", "product_update"}]
    product_rows = [[name(s.company_id), s.finding[:80], s.confidence] for s in product]
    hiring = [s for s in sigs if s.signal_type in {"hiring", "gtm"}]
    hiring_rows = [[name(s.company_id), s.finding[:80], s.confidence] for s in hiring]
    recs = [s for s in sigs if s.recommendation and s.recommendation.strip()]
    recs_parts = []
    for s in recs:
        recs_parts.append("- **" + name(s.company_id) + "** - " + s.recommendation + "\n")

    if citations:
        cite_lines = [str(i + 1) + ". " + c.get("url", "") + " - _" + c.get("snippet", "")[:120] + "_\n" for i, c in enumerate(citations)]
    else:
        cite_lines = ["_(citations populated by Phase 6 check_citations node)_\n"]

    parts = [
        "# Weekly Competitive Intelligence Report\n",
        "**Target:** " + target_company + "  |  **Date:** " + today + "  |  **Signals:** " + str(len(sigs)) + "\n",
        "## " + WEEKLY_SECTIONS[0] + "\n",
        summary_md,
        "\n## " + WEEKLY_SECTIONS[1] + "\n",
        "".join(key_changes_parts) if key_changes_parts else "_(no competitor changes observed)_\n",
        "\n## " + WEEKLY_SECTIONS[2] + "\n",
        _render_table(product_rows, ["competitor", "finding", "confidence"]),
        "\n## " + WEEKLY_SECTIONS[3] + "\n",
        _render_table(hiring_rows, ["competitor", "finding", "confidence"]),
        "\n## " + WEEKLY_SECTIONS[4] + "\n",
        "".join(recs_parts) if recs_parts else "_(no actionable recommendations this week)_\n",
        "\n## " + WEEKLY_SECTIONS[5] + "\n",
        "".join(cite_lines),
    ]
    return "".join(parts)


def render_battlecard(
    company_name: str,
    signals: Iterable[Signal],
    *,
    target_name: str,
    citations=None,
    extras=None,
) -> str:
    sigs = list(signals)
    today = _dt.date.today().isoformat()
    product = [s for s in sigs if s.signal_type in {"product", "product_update"}]
    hiring = [s for s in sigs if s.signal_type in {"hiring", "gtm"}]
    risks = [s for s in sigs if s.signal_type == "risk"]
    other = [s for s in sigs if s.signal_type not in {"product", "product_update", "hiring", "gtm", "risk"}]

    sections = {
        "Positioning": (
            "_Why " + company_name + " wins:_\n\n"
            + "\n".join("- " + s.finding for s in product[:3] if s.finding)
            + ("\n_(no product signals observed)_" if not product else "")
        ),
        "Key Strengths": "\n".join("- " + s.finding for s in product + other if s.finding) or "_(insufficient data)_",
        "Recent Moves": "\n".join("- " + s.finding for s in sigs if s.finding) or "_(no moves observed)_",
        "Risks & Weaknesses": "\n".join("- " + s.finding for s in risks + hiring if s.finding) or "_(none observed)_",
        "Suggested Sales Response": "\n".join("- " + s.recommendation for s in sigs if s.recommendation) or "_(TBD)_",
        "Attack Points": _render_attack_points(extras or {}),
        "Evidence Sources": (
            "\n".join(str(i + 1) + ". " + c.get("url", "") for i, c in enumerate(citations or []))
            or "_(citations populated by Phase 6)_\n"
        ),
    }
    parts = [
        "# Battlecard: " + company_name + "\n",
        "_vs " + target_name + "  |  " + today + "  |  " + str(len(sigs)) + " signals_\n",
    ]
    for title in BATTLECARD_SECTIONS:
        parts.append("\n## " + title + "\n" + sections.get(title, "") + "\n")
    return "".join(parts)


__all__ = ["render_weekly_report", "render_battlecard"]