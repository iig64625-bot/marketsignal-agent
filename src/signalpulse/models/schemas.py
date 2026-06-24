"""Pydantic schemas for LLM-structured outputs and API contracts."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EventOutput(BaseModel):
    """A single competitive-intelligence event extracted from a document."""

    event_type: str = Field(description="Type: product_update | github_release | pricing_change | hiring_change | user_feedback | partnership | announcement")
    title: str = Field(description="One-line event title")
    summary: str = Field(default="", description="Short factual summary")
    published_at: str | None = Field(default=None, description="ISO8601 date if known")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    evidence_spans: list[str] = Field(default_factory=list, description="Verbatim source spans supporting the event")


class EventListOutput(BaseModel):
    """Top-level wrapper for ``extract_events`` LLM output."""

    events: list[EventOutput] = Field(default_factory=list)


class SignalOutput(BaseModel):
    """A market signal derived from one or more events."""

    signal_type: str = Field(description="product | pricing | hiring | gtm | risk")
    finding: str = Field(description="Factual observation")
    analysis: str = Field(default="", description="Why this matters")
    recommendation: str = Field(default="", description="Concrete next action")
    confidence: str = Field(default="medium", description="high | medium | low")
    supporting_event_ids: list[str] = Field(default_factory=list)


class SignalListOutput(BaseModel):
    """Wrapper for ``analyze_signals`` LLM output."""

    signals: list[SignalOutput] = Field(default_factory=list)


class WeeklyReportSection(BaseModel):
    """A single section in a weekly report."""

    section_title: str
    items: list[dict[str, Any]] = Field(default_factory=list)


class WeeklyReportOutput(BaseModel):
    """Structured weekly report (before markdown rendering)."""

    title: str
    period: str = ""
    sections: list[WeeklyReportSection] = Field(default_factory=list)
    citations: list[dict[str, str]] = Field(default_factory=list)


class BattlecardSection(BaseModel):
    section_title: str
    items: list[str] = Field(default_factory=list)


class BattlecardOutput(BaseModel):
    """Structured battlecard (before markdown rendering)."""

    competitor_name: str
    positioning: str = ""
    sections: list[BattlecardSection] = Field(default_factory=list)
    evidence: list[dict[str, str]] = Field(default_factory=list)


class CitationCheckResult(BaseModel):
    """Per-claim citation check verdict."""

    claim_text: str
    claim_type: str = "fact"
    is_supported: bool = False
    supporting_urls: list[str] = Field(default_factory=list)
    notes: str = ""


class FaithfulnessCheck(BaseModel):
    """LLM judgement of how faithfully a summary reflects its source."""

    score: float = Field(ge=0.0, le=1.0, description="Faithfulness score in [0, 1].")
    notes: str = Field(default="", description="Short justification.")


class AttackPoint(BaseModel):
    """A specific weakness the sales team can exploit."""

    weakness: str = Field(description="The competitor's weakness, phrased factually.")
    evidence: str = Field(default="", description="Signal or evidence that supports this attack point.")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence in the attack point.")


class SalesTalkTrack(BaseModel):
    """A specific conversation line for sales."""

    situation: str = Field(default="", description="When to use this line (e.g. 'when prospect mentions price').")
    line: str = Field(description="The actual sales line to say.")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class BattlecardExtras(BaseModel):
    """LLM-generated extras for a sales battlecard."""

    sales_pitch: str = Field(default="", description="Top-of-card elevator pitch for the sales team.")
    attack_points: list[AttackPoint] = Field(default_factory=list, description="3-5 weaknesses to exploit.")
    talk_tracks: list[SalesTalkTrack] = Field(default_factory=list, description="3-5 specific conversation lines.")
    summary: str = Field(default="", description="One-sentence TL;DR for the sales rep.")


__all__ = [
    "EventOutput",
    "EventListOutput",
    "SignalOutput",
    "SignalListOutput",
    "CitationCheckResult",
    "FaithfulnessCheck",
    "AttackPoint",
    "SalesTalkTrack",
    "BattlecardExtras",
]
