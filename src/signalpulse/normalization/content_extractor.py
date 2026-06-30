"""Convert a :class:`RawDocument` into a :class:`NormalizedDocument`."""
from __future__ import annotations

import datetime as _dt
import hashlib
import re
from pathlib import Path

from langdetect.lang_detect_exception import LangDetectException
from loguru import logger

from signalpulse.models.base import new_id
from signalpulse.models.normalized_document import NormalizedDocument
from signalpulse.models.raw_document import RawDocument
from signalpulse.normalization.html_cleaner import clean_html

_PUBLISHED_PATTERNS = [
    re.compile(r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']', re.I),
    re.compile(r'<meta[^>]+name=["\']pubdate["\'][^>]+content=["\']([^"\']+)["\']', re.I),
    re.compile(r'<meta[^>]+name=["\']date["\'][^>]+content=["\']([^"\']+)["\']', re.I),
]

_SOURCE_CATEGORY = {
    "changelog": "product_update",
    "blog": "announcement",
    "jobs": "hiring",
    "docs": "documentation",
    "github": "github_release",
    "rss": "announcement",
    "website": "general",
    "pricing": "pricing",
}


def _read_raw(raw: RawDocument) -> str:
    if raw.raw_html_path and Path(raw.raw_html_path).exists():
        return Path(raw.raw_html_path).read_text(encoding="utf-8", errors="ignore")
    if raw.raw_text_path and Path(raw.raw_text_path).exists():
        return Path(raw.raw_text_path).read_text(encoding="utf-8", errors="ignore")
    return ""


def _parse_published(text: str) -> _dt.datetime | None:
    for pat in _PUBLISHED_PATTERNS:
        m = pat.search(text)
        if m:
            try:
                from dateutil import parser as _p  # type: ignore

                return _p.parse(m.group(1))
            except (ValueError, OverflowError, UnicodeDecodeError) as exc:
                logger.debug("content_extractor: skip unparseable timestamp: {}", exc)
                continue
    return None


def extract_content(raw: RawDocument, *, company_id: str) -> NormalizedDocument:
    """Build a :class:`NormalizedDocument` from a :class:`RawDocument`."""
    raw_text = _read_raw(raw)
    is_html = "<" in raw_text and ">" in raw_text
    clean = clean_html(raw_text) if is_html else raw_text
    title = ""
    if is_html:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(raw_text, "html.parser")
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
    if not title:
        title = raw.url.rsplit("/", 1)[-1] or "untitled"
    content_hash = hashlib.sha256(clean.encode("utf-8")).hexdigest()
    try:
        from langdetect import detect

        language = detect(clean[:4000]) if clean else "en"
    except LangDetectException as exc:
        logger.debug("content_extractor: language detect failed, default to en: {}", exc)
        language = "en"
    published = _parse_published(raw_text)
    category = _SOURCE_CATEGORY.get(raw.content_type or "", "general") if raw.content_type else "general"
    return NormalizedDocument(
        id=new_id(),
        raw_document_id=raw.id,
        company_id=company_id,
        source_type=raw.content_type or "unknown",
        title=title[:512],
        clean_text=clean,
        language=language or "en",
        published_at=published,
        canonical_url=raw.url,
        content_hash=content_hash,
        dedup_group=None,
        category=category,
        confidence=1.0,
    )
