"""Tests for the chunker."""

from __future__ import annotations

from signalpulse.models.base import new_id
from signalpulse.models.normalized_document import NormalizedDocument
from signalpulse.rag.chunker import _count_tokens, chunk_document


def _make_doc(text: str) -> NormalizedDocument:
    return NormalizedDocument(
        id=new_id(),
        raw_document_id="r",
        company_id="c1",
        source_type="blog",
        title="t",
        clean_text=text,
    )


def test_count_tokens_positive_for_nonempty():
    assert _count_tokens("hello world") > 0


def test_chunk_document_short_text_single_chunk():
    doc = _make_doc("short text")
    chunks = chunk_document(doc, max_tokens=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].chunk_text == "short text"
    assert chunks[0].chunk_index == 0


def test_chunk_document_long_text_overlaps():
    text = ("sentence " * 200).strip()
    doc = _make_doc(text)
    chunks = chunk_document(doc, max_tokens=50, overlap=10)
    assert len(chunks) >= 2
    assert all(c.token_count <= 50 for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(c.document_id == doc.id for c in chunks)


def test_chunk_document_empty_returns_empty_list():
    doc = _make_doc("")
    assert chunk_document(doc) == []
