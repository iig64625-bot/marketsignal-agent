"""RSS / Atom feed fetcher."""
from __future__ import annotations

from typing import Any

import feedparser
from loguru import logger

from signalpulse.ingestion.http_client import HttpClient, checksum_bytes
from signalpulse.models.base import new_id, utcnow
from signalpulse.models.raw_document import RawDocument


def _entry_to_raw(
    entry: dict[str, Any],
    *,
    source_id: str,
    crawl_run_id: str,
    body: bytes,
    feed_title: str,
) -> RawDocument:
    url = entry.get("link") or entry.get("id") or ""
    title = entry.get("title", "")
    summary = entry.get("summary", "")
    text = f"{title}\n\n{summary}\n\n{url}"
    return RawDocument(
        id=new_id(),
        crawl_run_id=crawl_run_id,
        source_id=source_id,
        url=url,
        http_status=200,
        fetched_at=utcnow(),
        content_type="application/rss+xml",
        raw_text_path=None,
        raw_html_path=None,
        checksum=checksum_bytes(text.encode("utf-8")),
    )


async def fetch_rss(
    url: str,
    source_id: str,
    crawl_run_id: str,
    *,
    client: HttpClient | None = None,
) -> list[RawDocument]:
    """Parse an RSS / Atom feed and return one ``RawDocument`` per entry.

    The raw feed body is not persisted on disk; each entry's title + summary
    becomes a virtual ``RawDocument`` for downstream normalization.
    """
    own_client = client is None
    if own_client:
        client = HttpClient()
        await client.__aenter__()
    try:
        body = await client.fetch_bytes(url)
        parsed = feedparser.parse(body)
        out: list[RawDocument] = []
        for entry in parsed.entries:
            out.append(
                _entry_to_raw(
                    entry,
                    source_id=source_id,
                    crawl_run_id=crawl_run_id,
                    body=body,
                    feed_title=parsed.feed.get("title", ""),
                )
            )
        logger.info("rss parsed: url={} entries={}", url, len(out))
        return out
    finally:
        if own_client:
            await client.__aexit__(None, None, None)
