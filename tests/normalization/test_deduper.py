"""Tests for the deduper."""

from __future__ import annotations

import datetime as _dt

from signalpulse.models.base import new_id
from signalpulse.models.normalized_document import NormalizedDocument
from signalpulse.normalization.deduper import deduplicate


def _make(company: str, content_hash: str, when: _dt.datetime | None) -> NormalizedDocument:
    nd = NormalizedDocument(
        id=new_id(),
        raw_document_id="r",
        company_id=company,
        source_type="website",
        title="t",
        clean_text="x",
        content_hash=content_hash,
    )
    if when:
        nd.published_at = when
    return nd


def test_dedup_keeps_newest_and_marks_group():
    older = _make("c1", "h1", _dt.datetime(2025, 1, 1))
    newer = _make("c1", "h1", _dt.datetime(2025, 1, 2))
    out = deduplicate([older, newer])
    survivors = [d for d in out if d.dedup_group == "h1"]
    assert len(survivors) == 1
    assert survivors[0].id == newer.id


def test_dedup_unique_docs_get_their_own_group():
    a = _make("c1", "h1", None)
    b = _make("c1", "h2", None)
    deduplicate([a, b])
    result = deduplicate([a, b])
    assert {d.dedup_group for d in result} == {"h1", "h2"}

def test_dedup_groups_per_company():
    """The same content hash under different companies is NOT a duplicate."""
    a = _make("c1", "h1", None)
    b = _make("c2", "h1", None)
    deduplicate([a, b])
    assert a.dedup_group == "h1"
    assert b.dedup_group == "h1"

