"""Tests for the content extractor."""

from __future__ import annotations

import datetime as _dt

from signalpulse.models.base import new_id
from signalpulse.models.normalized_document import NormalizedDocument
from signalpulse.models.raw_document import RawDocument
from signalpulse.normalization.content_extractor import extract_content


def test_extract_content_reads_raw_html(tmp_path):
    raw_path = tmp_path / "page.html"
    raw_path.write_text(
        "<html><head><title>News</title>"
        '<meta property="article:published_time" content="2025-01-02T03:04:05Z" />'
        "</head><body><p>Hello world</p></body></html>",
        encoding="utf-8",
    )
    raw = RawDocument(
        id=new_id(),
        crawl_run_id="r",
        source_id="s",
        url="https://x.test/news",
        http_status=200,
        fetched_at=_dt.datetime.utcnow(),
        content_type="text/html",
        raw_html_path=str(raw_path),
        raw_text_path=None,
        checksum="abc",
    )
    nd = extract_content(raw, company_id="c1")
    assert isinstance(nd, NormalizedDocument)
    assert nd.title == "News"
    assert "Hello world" in nd.clean_text
    assert nd.published_at is not None
    assert nd.published_at.year == 2025  # type: ignore[union-attr]
    assert nd.canonical_url == "https://x.test/news"
    assert nd.content_hash and len(nd.content_hash) == 64


def test_extract_content_handles_missing_file():
    raw = RawDocument(
        id=new_id(),
        crawl_run_id="r",
        source_id="s",
        url="https://x.test/missing",
        http_status=200,
        fetched_at=_dt.datetime.utcnow(),
        content_type="text/html",
        raw_html_path="/nonexistent/path.html",
        raw_text_path=None,
        checksum="x",
    )
    nd = extract_content(raw, company_id="c1")
    assert nd.clean_text == ""  # gracefully empty
    assert nd.title  # falls back to URL slug
