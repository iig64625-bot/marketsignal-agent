"""Source-type router that dispatches to the correct fetcher."""
from __future__ import annotations

from loguru import logger

from signalpulse.ingestion.fetch_github import fetch_github_releases
from signalpulse.ingestion.fetch_rss import fetch_rss
from signalpulse.ingestion.fetch_webpage import fetch_webpage
from signalpulse.ingestion.http_client import HttpClient
from signalpulse.models.raw_document import RawDocument
from signalpulse.models.source import Source

WEBPAGE_TYPES = {"website", "blog", "changelog", "docs", "jobs", "pricing"}


async def fetch_source(
    source: Source,
    crawl_run_id: str,
    *,
    client: HttpClient | None = None,
) -> list[RawDocument]:
    """Dispatch a :class:`Source` to the fetcher matching its ``source_type``.

    Returns an empty list (and logs a warning) for unknown source types so the
    rest of the pipeline can continue.
    """
    t = source.source_type
    try:
        if t in WEBPAGE_TYPES:
            return [await fetch_webpage(source.url, source.id, crawl_run_id, client=client)]
        if t == "rss":
            return await fetch_rss(source.url, source.id, crawl_run_id, client=client)
        if t == "github":
            return await fetch_github_releases(source.url, source.id, crawl_run_id, client=client)
        logger.warning("unknown source_type={} source_id={} url={}", t, source.id, source.url)
        return []
    except Exception as exc:  # noqa: BLE001 - we want to keep the pipeline alive
        logger.error("fetch failed: type={} url={} err={}", t, source.url, exc)
        return []
