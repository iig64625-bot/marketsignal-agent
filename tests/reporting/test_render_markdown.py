"""Tests for the report renderer."""

from __future__ import annotations

from signalpulse.models.base import new_id
from signalpulse.models.signal import Signal
from signalpulse.reporting.render_markdown import render_battlecard, render_weekly_report
from signalpulse.reporting.templates import BATTLECARD_SECTIONS, WEEKLY_SECTIONS


def _sig(
    company_id: str = "c1",
    signal_type: str = "product",
    finding: str = "X",
    analysis: str = "Y",
    recommendation: str = "Z",
    confidence: str = "high",
) -> Signal:
    return Signal(
        id=new_id(),
        crawl_run_id="r1",
        company_id=company_id,
        signal_type=signal_type,
        finding=finding,
        analysis=analysis,
        recommendation=recommendation,
        confidence=confidence,
    )


def test_weekly_report_includes_all_six_sections():
    """The weekly report contains every section from the template list."""
    md = render_weekly_report(
        [_sig()],
        target_company="Dify",
        company_name_lookup={"c1": "Coze"},
    )
    for section in WEEKLY_SECTIONS:
        assert f"## {section}" in md, f"missing section: {section}"


def test_weekly_report_groups_signals_by_competitor():
    md = render_weekly_report(
        [_sig(company_id="c1", finding="A"), _sig(company_id="c2", finding="B")],
        target_company="Dify",
        company_name_lookup={"c1": "Coze", "c2": "FastGPT"},
    )
    assert "### Coze" in md
    assert "### FastGPT" in md
    assert "A" in md and "B" in md


def test_weekly_report_citations_render_when_provided():
    md = render_weekly_report(
        [_sig()],
        target_company="Dify",
        citations=[{"url": "https://x.test/a", "snippet": "alpha"}, {"url": "https://x.test/b", "snippet": "beta"}],
    )
    assert "https://x.test/a" in md
    assert "https://x.test/b" in md
    assert "1." in md and "2." in md


def test_weekly_report_handles_empty_signals():
    md = render_weekly_report([], target_company="Dify")
    assert "0**" in md or "**0**" in md  # zero signals
    for section in WEEKLY_SECTIONS:
        assert f"## {section}" in md


def test_battlecard_includes_all_six_sections():
    md = render_battlecard([_sig()], company_name="Coze", target_name="Dify")
    for section in BATTLECARD_SECTIONS:
        assert f"## {section}" in md, f"missing section: {section}"


def test_battlecard_includes_company_and_target_names():
    md = render_battlecard([_sig(finding="won X")], company_name="Coze", target_name="Dify")
    assert "Coze" in md
    assert "Dify" in md
    assert "won X" in md
