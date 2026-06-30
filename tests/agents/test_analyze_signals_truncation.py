"""Tests for Task C: prompt truncation in analyze_signals._build_prompt."""
from __future__ import annotations

from datetime import datetime, timezone

from signalpulse.agents.nodes.analyze_signals import (
    MAX_EVENTS_PER_COMPETITOR,
    MAX_SUMMARY_CHARS,
    MAX_TITLE_CHARS,
    _build_prompt,
)
from signalpulse.models.event import Event


def _mk_event(i: int, *, title: str = "T", summary: str = "S") -> Event:
    """Build a tiny Event for unit testing the prompt builder."""
    return Event(
        id=f"e{i:04d}",
        document_id="d1",
        company_id="c1",
        event_type="product_update",
        title=title,
        summary=summary,
        published_at=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
        confidence=0.9,
    )


def test_long_title_is_truncated_to_max() -> None:
    """A 5000-char title becomes at most MAX_TITLE_CHARS chars in the prompt."""
    long_title = "X" * 5000
    prompt = _build_prompt("Acme", [_mk_event(1, title=long_title)])
    # The literal "XXXXX" of length MAX_TITLE_CHARS should appear, longer should not.
    assert ("X" * (MAX_TITLE_CHARS + 1)) not in prompt
    assert ("X" * MAX_TITLE_CHARS) in prompt


def test_long_summary_is_truncated_to_max() -> None:
    """A 5000-char summary becomes at most MAX_SUMMARY_CHARS chars in the prompt."""
    long_summary = "Y" * 5000
    prompt = _build_prompt("Acme", [_mk_event(1, summary=long_summary)])
    assert ("Y" * (MAX_SUMMARY_CHARS + 1)) not in prompt
    assert ("Y" * MAX_SUMMARY_CHARS) in prompt


def test_none_title_and_summary_do_not_crash() -> None:
    """A None title / summary should be treated as empty string, not raise."""
    e = Event(
        id="enull",
        document_id="d1",
        company_id="c1",
        event_type="product_update",
        title=None,  # type: ignore[arg-type]
        summary=None,  # type: ignore[arg-type]
        published_at=None,
        confidence=0.5,
    )
    prompt = _build_prompt("Acme", [e])
    assert "id=enull" in prompt
    assert "title=" in prompt
    assert "summary=" in prompt


def test_truncated_flag_adds_a_note() -> None:
    """When the caller passes truncated=True, the prompt explains the drop."""
    prompt = _build_prompt("Acme", [_mk_event(1)], truncated=True)
    assert "most recent events" in prompt


def test_truncated_flag_absent_by_default() -> None:
    """By default, no truncation note is added (the caller signals it)."""
    prompt = _build_prompt("Acme", [_mk_event(1)])
    assert "most recent events" not in prompt


def test_max_events_per_competitor_constant_is_sane() -> None:
    """The cap is small enough to keep prompts bounded (50 events * 80 tokens ~ 4k tokens)."""
    assert 10 <= MAX_EVENTS_PER_COMPETITOR <= 100
