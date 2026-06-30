"""Render weekly reports and battlecards as Markdown (Chinese)."""
from __future__ import annotations

import datetime as _dt
from collections import Counter, defaultdict
from collections.abc import Iterable

from signalpulse.models.signal import Signal
from signalpulse.reporting.templates import (
    BATTLECARD_SECTIONS,
    SIGNAL_TYPE_LABELS,
    WEEKLY_SECTIONS,
    label_signal_type,
)


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


def _cn_confidence(c: str | None) -> str:
    return {"high": "高", "medium": "中", "low": "低"}.get((c or "").lower(), c or "?")


def _render_table(rows, headers):
    if not rows:
        return "_(无数据)_\n"
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines) + "\n"


def _render_attack_points(extras):
    if not extras:
        return "_(无 LLM 生成的进攻点；请配置 LLM 获得更丰富内容)_\n"
    attack_points = extras.get("attack_points") or []
    talk_tracks = extras.get("talk_tracks") or []
    pitch = extras.get("sales_pitch") or ""
    summary = extras.get("summary") or ""
    out = []
    if summary:
        out.append("**摘要：** " + summary)
    if pitch:
        out.append("**电梯演讲：** " + pitch)
    if attack_points:
        out.append("")
        for ap in attack_points:
            if not isinstance(ap, dict):
                continue
            weakness = ap.get("weakness", "")
            evidence = ap.get("evidence", "")
            conf = ap.get("confidence", 0.5)
            if weakness:
                line = "- " + weakness + " _(可信度：" + f"{conf:.0%}" + ")_"
                if evidence:
                    line += " - " + evidence
                out.append(line)
    if talk_tracks:
        out.append("")
        out.append("**话术：**")
        for t in talk_tracks:
            if not isinstance(t, dict):
                continue
            situation = t.get("situation", "")
            line_text = t.get("line", "")
            if line_text:
                if situation:
                    out.append("- _场景：_ " + situation + " -> _话术：_ " + line_text)
                else:
                    out.append("- " + line_text)
    if not out:
        return "_(无 LLM 进攻点)_\n"
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
    type_rows = [
        [label_signal_type(k), str(v)]
        for k, v in sorted(by_type.items(), key=lambda x: -x[1])
    ]
    company_rows = [
        [name(c), str(len(g))]
        for c, g in sorted(by_company.items(), key=lambda x: -len(x[1]))
    ]
    high = sum(1 for s in sigs if s.confidence == "high")
    summary_md = (
        "本周 pipeline 在 **{t}** 的 **{m}** 个竞品中观察到 **{n}** 个市场信号，其中 **{h}** 个高可信度。\n\n"
        "### 按信号类型\n{table1}### 按竞品\n{table2}"
    ).format(
        n=len(sigs),
        m=len(by_company),
        t=target_company,
        h=high,
        table1=_render_table(type_rows, ["信号类型", "数量"]),
        table2=_render_table(company_rows, ["竞品", "数量"]),
    )

    key_changes_parts = []
    for cid, group in sorted(by_company.items(), key=lambda x: -len(x[1])):
        key_changes_parts.append("### " + name(cid) + "\n")
        for s in group:
            key_changes_parts.append(
                "- **[" + label_signal_type(s.signal_type) + "]** "
                + s.finding
                + " _(可信度：" + _cn_confidence(s.confidence) + ")_\n"
            )
            if s.analysis:
                key_changes_parts.append("  - 分析：" + s.analysis + "\n")
        key_changes_parts.append("")

    product = [s for s in sigs if s.signal_type in {"product", "product_update"}]
    product_rows = [
        [name(s.company_id), s.finding[:80], _cn_confidence(s.confidence)] for s in product
    ]
    hiring = [s for s in sigs if s.signal_type in {"hiring", "gtm"}]
    hiring_rows = [
        [name(s.company_id), s.finding[:80], _cn_confidence(s.confidence)] for s in hiring
    ]
    recs = [s for s in sigs if s.recommendation and s.recommendation.strip()]
    recs_parts = []
    for s in recs:
        recs_parts.append(
            "- **" + name(s.company_id) + "** - " + s.recommendation + "\n"
        )

    if citations:
        cite_lines = []
        for i, c in enumerate(citations, 1):
            url = c.get("url", "")
            if url:
                cite_lines.append(str(i) + ". " + url)
        citations_block = "\n".join(cite_lines) or "_(引用由 Phase 6 check_citations 节点填充)_"
    else:
        citations_block = "_(引用由 Phase 6 check_citations 节点填充)_"

    sections = {
        "执行摘要": summary_md,
        "按竞品的关键变化": "".join(key_changes_parts) or "_(本周无竞品变化)_",
        "产品更新信号": _render_table(product_rows, ["竞品", "信号内容", "可信度"]),
        "招聘与 GTM 信号": _render_table(hiring_rows, ["竞品", "信号内容", "可信度"]),
        "行动建议": "".join(recs_parts) or "_(本周无具体建议)_",
        "引用": citations_block,
    }
    parts = [
        "# 周报：竞品情报\n",
        "**目标：** " + target_company + "  |  **日期：** " + today + "  |  **信号：** " + str(len(sigs)) + "\n",
    ]
    for title in WEEKLY_SECTIONS:
        parts.append("\n## " + title + "\n" + sections.get(title, "") + "\n")
    return "".join(parts)


def render_battlecard(
    signals: Iterable[Signal],
    *,
    company_name: str,
    target_name: str,
    extras: dict | None = None,
    citations=None,
) -> str:
    sigs = list(signals)
    today = _dt.date.today().isoformat()
    n = len(sigs)

    positioning = sigs[0].finding if sigs else "_(无定位信息)_"
    if len(sigs) > 1:
        positioning += " / " + sigs[1].finding[:60]
    strengths = [s for s in sigs if s.signal_type in {"product", "product_update", "ecosystem"}]
    strengths_text = "\n".join(
        "- " + s.finding for s in strengths[:5]
    ) or "_(本周未观察到)_"
    recent = [s for s in sigs if s.signal_type not in {"risk"}]
    recent_text = "\n".join(
        "- [" + label_signal_type(s.signal_type) + "] " + s.finding for s in recent[:8]
    ) or "_(本周未观察到)_"
    risks = [s for s in sigs if s.signal_type in {"risk", "user_feedback"}]
    risks_text = "\n".join(
        "- " + s.finding for s in risks
    ) or "_(本周未观察到)_"
    suggested = "\n".join(
        "- " + s.recommendation for s in sigs if s.recommendation
    ) or "_(待定)_"

    if citations:
        cite_lines = [str(i + 1) + ". " + c.get("url", "") for i, c in enumerate(citations) if c.get("url")]
        evidence_block = "\n".join(cite_lines) or "_(引用由 Phase 6 填充)\n"
    else:
        evidence_block = "_(引用由 Phase 6 填充)\n"

    sections = {
        "定位": positioning,
        "核心优势": strengths_text,
        "近期动作": recent_text,
        "风险与弱点": risks_text,
        "建议销售话术": suggested,
        "进攻点": _render_attack_points(extras or {}),
        "证据来源": evidence_block,
    }
    parts = [
        "# 竞品卡片：" + company_name + "\n",
        "_对比 " + target_name + "  |  " + today + "  |  " + str(n) + " 条信号_\n",
    ]
    for title in BATTLECARD_SECTIONS:
        parts.append("\n## " + title + "\n" + sections.get(title, "") + "\n")
    return "".join(parts)


__all__ = ["render_weekly_report", "render_battlecard"]