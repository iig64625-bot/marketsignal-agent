"""Tests for eval metric helpers."""

from __future__ import annotations

from signalpulse.evals.citation_coverage import citation_coverage
from signalpulse.evals.dedup_rate import dedup_rate
from signalpulse.evals.token_cost import token_cost
from signalpulse.evals.unsupported_claims import unsupported_claim_rate
from signalpulse.models.claim import Claim
from signalpulse.models.normalized_document import NormalizedDocument


def _claim(supported: bool) -> Claim:
    return Claim(id="x", report_id="r", claim_text="c", is_supported=supported, confidence=0.5)


def _doc(group: str | None) -> NormalizedDocument:
    return NormalizedDocument(
        id="d", raw_document_id="r", company_id="c", source_type="x",
        title="t", clean_text="x", dedup_group=group,
    )


def test_citation_coverage_all_supported():
    assert citation_coverage([_claim(True), _claim(True), _claim(True)]) == 1.0


def test_citation_coverage_mixed():
    from pytest import approx

    assert citation_coverage([_claim(True), _claim(False), _claim(False)]) == approx(1 / 3)


def test_citation_coverage_empty():
    assert citation_coverage([]) == 1.0


def test_unsupported_claim_rate():
    from pytest import approx

    assert unsupported_claim_rate([_claim(False), _claim(False), _claim(True)]) == approx(2 / 3)


def test_dedup_rate_counts_unique_groups():
    from pytest import approx

    docs = [_doc("h1"), _doc("h1"), _doc("h2"), _doc(None), _doc(None)]
    # unique (group != None) = 2, total = 5
    assert dedup_rate(docs) == approx(3 / 5)


def test_token_cost_known_model():
    # gpt-4o-mini: 0.00015 in / 0.0006 out per 1K
    cost = token_cost(tokens_in=1000, tokens_out=500, model="gpt-4o-mini")
    # 1 * 0.00015 + 0.5 * 0.0006 = 0.00015 + 0.0003 = 0.00045
    from pytest import approx

    assert cost == approx(0.00045)


def test_token_cost_unknown_model_uses_default():
    from pytest import approx

    cost = token_cost(tokens_in=1000, tokens_out=1000, model="unknown-model-xyz")
    # default (0.001, 0.002) -> 0.001 + 0.002 = 0.003
    assert cost == approx(0.003)
