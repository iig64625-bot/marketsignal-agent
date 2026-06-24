"""Tests for the citation checker (LLM is mocked)."""

from __future__ import annotations

import pytest

from signalpulse.citation.checker import (
    _deterministic_support,
    _split_claims_from_markdown,
    compute_citation_metrics,
)
from signalpulse.models.claim import Claim


def test_split_claims_filters_headings_and_placeholders():
    md = (
        "# Heading\n"
        "A real claim about Coze releasing v2.5 on Tuesday afternoon.\n"
        "_(no signals)_\n"
        "| col1 | col2 |\n| --- | --- |\n"
        "Another real claim about pricing changes in Coze last week.\n"
    )
    claims = _split_claims_from_markdown(md)
    assert any("v2.5" in c for c in claims)
    assert not any("_(no signals)_" in c for c in claims)
    assert not any(c.startswith("|") for c in claims)


def test_split_claims_respects_max():
    md = "Sentence one. " * 100
    claims = _split_claims_from_markdown(md, max_claims=3)
    assert len(claims) <= 3


def test_deterministic_support_overlap_positive():
    claim = "Coze released a new workflow template yesterday"
    evidence = [("Coze released a new workflow template today.", "https://x")]
    assert _deterministic_support(claim, evidence)[0] is True


def test_deterministic_support_overlap_negative():
    claim = "Coze released a new workflow template yesterday"
    evidence = [("FastGPT launched a dashboard update.", "https://x")]
    assert _deterministic_support(claim, evidence)[0] is False


def test_compute_citation_metrics_empty():
    m = compute_citation_metrics([])
    assert m["citation_coverage"] == 1.0
    assert m["unsupported_claim_rate"] == 0.0


def test_compute_citation_metrics_with_claims():
    claims = [
        Claim(id="a", report_id="r", claim_text="x", is_supported=True, confidence=0.9),
        Claim(id="b", report_id="r", claim_text="y", is_supported=False, confidence=0.3),
        Claim(id="c", report_id="r", claim_text="z", is_supported=True, confidence=0.8),
    ]
    m = compute_citation_metrics(claims)
    assert m["citation_coverage"] == pytest.approx(2 / 3)
    assert m["unsupported_claim_rate"] == pytest.approx(1 / 3)
    assert m["total_claims"] == 3
