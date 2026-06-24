"""Generic webpage fetcher."""
from __future__ import annotations

from pathlib import Path

from marketsignal.ingestion.http_client import HttpClient, checksum_bytes
from marketsignal.models.base import new_id, utcnow
from marketsignal.models.raw_document import RawDocument


def _raw_dir(root: Path, crawl_run_id: str) -> Path:
    d = root / "data" / "raw" / crawl_run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


async def fetch_webpage(
    url: str,
    source_id: str,
    crawl_run_id: str,
    *,
    client: HttpClient | None = None,
    raw_root: Path | None = None,
) -> RawDocument:
    """Download ``url`` and persist the raw HTML alongside a ``RawDocument`` row.

    Args:
        url: Target URL to download.
        source_id: Owning ``Source.id`` (foreign key for the returned row).
        crawl_run_id: Owning ``CrawlRun.id``.
        client: Optional pre-configured :class:`HttpClient` (for tests / pooling).
        raw_root: Optional override for where raw files are written.

    Returns:
        An unsaved :class:`RawDocument` ORM object. The caller is responsible
        for adding it to a session and committing.
    """
    own_client = client is None
    if own_client:
        client = HttpClient()
        await client.__aenter__()
    try:
        response = await client.fetch(url)
        body = response.content
        ts = utcnow()
        suffix = ".html"
        content_type = response.headers.get("content-type", "")
        if "xml" in content_type or url.endswith(".xml"):
            suffix = ".xml"
        elif "json" in content_type or url.endswith(".json"):
            suffix = ".json"
        if raw_root is None:
            raw_root = Path.cwd()
        target = _raw_dir(raw_root, crawl_run_id) / f"{source_id}_{int(ts.timestamp() * 1000)}{suffix}"
        target.write_bytes(body)
        return RawDocument(
            id=new_id(),
            crawl_run_id=crawl_run_id,
            source_id=source_id,
            url=url,
            http_status=response.status_code,
            fetched_at=ts,
            content_type=content_type or None,
            raw_html_path=str(target) if suffix == ".html" else None,
            raw_text_path=str(target) if suffix != ".html" else None,
            checksum=checksum_bytes(body),
        )
    finally:
        if own_client:
            await client.__aexit__(None, None, None)
