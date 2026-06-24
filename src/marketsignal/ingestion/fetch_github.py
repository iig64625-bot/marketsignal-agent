"""GitHub releases fetcher."""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from loguru import logger

from marketsignal.ingestion.http_client import HttpClient, checksum_bytes
from marketsignal.models.base import new_id, utcnow
from marketsignal.models.raw_document import RawDocument

_REPO_RE = re.compile(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")


def parse_repo_url(url: str) -> tuple[str, str]:
    """Return ``(owner, repo)`` from a GitHub URL or raise ``ValueError``."""
    m = _REPO_RE.search(url.strip())
    if not m:
        raise ValueError(f"not a recognizable GitHub repo URL: {url!r}")
    return m.group(1), m.group(2)


async def fetch_github_releases(
    repo_url: str,
    source_id: str,
    crawl_run_id: str,
    *,
    client: HttpClient | None = None,
    raw_root: Path | None = None,
    max_releases: int = 20,
) -> list[RawDocument]:
    """Fetch releases for the repo at ``repo_url`` and return one row each.

    The raw JSON from the GitHub API is also persisted under
    ``data/raw/<crawl_run_id>/<source_id>_<timestamp>.json`` for auditability.
    """
    owner, repo = parse_repo_url(repo_url)
    own_client = client is None
    if own_client:
        client = HttpClient()
        await client.__aenter__()
    try:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page={max_releases}"
        body = await client.fetch_bytes(api_url)
        if raw_root is None:
            raw_root = Path.cwd()
        target = _raw_dir(raw_root, crawl_run_id) / f"{source_id}_{int(_dt.datetime.now(_dt.timezone.utc).timestamp() * 1000)}.json"
        target.write_bytes(body)
        releases = json.loads(body)
        if not isinstance(releases, list):
            logger.warning("github api returned non-list: repo={} type={}", repo_url, type(releases))
            return []
        out: list[RawDocument] = []
        for rel in releases:
            tag = rel.get("tag_name", "")
            name = rel.get("name") or tag
            body_md = rel.get("body") or ""
            text = f"# {name} ({tag})\n\n{body_md}\n\n{rel.get('html_url', '')}"
            out.append(
                RawDocument(
                    id=new_id(),
                    crawl_run_id=crawl_run_id,
                    source_id=source_id,
                    url=rel.get("html_url", api_url),
                    http_status=200,
                    fetched_at=utcnow(),
                    content_type="application/json",
                    raw_text_path=str(target),
                    raw_html_path=None,
                    checksum=checksum_bytes(text.encode("utf-8")),
                )
            )
        logger.info("github releases: repo={} count={}", repo_url, len(out))
        return out
    finally:
        if own_client:
            await client.__aexit__(None, None, None)


def _raw_dir(root: Path, crawl_run_id: str) -> Path:
    d = root / "data" / "raw" / crawl_run_id
    d.mkdir(parents=True, exist_ok=True)
    return d
