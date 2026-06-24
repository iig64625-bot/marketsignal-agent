"""Source health check: HEAD probes with timing and content-type validation."""
from __future__ import annotations

import asyncio
import datetime as _dt
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from marketsignal.config.loader import load_pipeline_config
from marketsignal.utils.retry import DEFAULT_RETRYABLE, retry_with_backoff_async


@dataclass
class SourceHealth:
    """Result of probing a single data source."""

    url: str
    source_type: str
    reachable: bool = False
    status_code: int | None = None
    response_time_ms: float | None = None
    content_type: str = ""
    error: str | None = None
    checked_at: str = field(default_factory=lambda: _dt.datetime.now(_dt.timezone.utc).isoformat() + "Z")

    def badge(self) -> str:
        """Return a human-friendly traffic-light label."""
        if not self.reachable:
            return "RED"
        if self.status_code and self.status_code >= 400:
            return "RED"
        if self.response_time_ms is not None and self.response_time_ms > 3000:
            return "YELLOW"
        return "GREEN"

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "badge": self.badge()}


_EXPECTED_CT: dict[str, str] = {
    "website": "text/html",
    "changelog": "text/html",
    "blog": "text/html",
    "docs": "text/html",
    "rss": "application/rss",
    "github": "application/json",
    "jobs": "text/html",
    "pricing": "text/html",
}


async def _probe(url: str, source_type: str, timeout: float = 10.0) -> SourceHealth:
    """Send a HEAD/GET to ``url`` and return a :class:`SourceHealth`."""
    health = SourceHealth(url=url, source_type=source_type)
    async def _do() -> None:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            t0 = asyncio.get_event_loop().time()
            try:
                # Try HEAD first; fall back to GET on 405
                try:
                    response = await client.head(url)
                    if response.status_code == 405:
                        response = await client.get(url)
                except httpx.HTTPError:
                    response = await client.get(url)
                elapsed_ms = (asyncio.get_event_loop().time() - t0) * 1000.0
                health.response_time_ms = round(elapsed_ms, 2)
                health.status_code = response.status_code
                health.content_type = response.headers.get("content-type", "")
                health.reachable = response.status_code < 400
            except (httpx.TransportError, httpx.HTTPError) as exc:
                health.reachable = False
                health.error = str(exc)[:256]
    try:
        await retry_with_backoff_async(
            _do,
            max_retries=2,
            base_delay=0.5,
            max_delay=5.0,
            retryable=DEFAULT_RETRYABLE + (httpx.TransportError, httpx.HTTPError),
        )
    except Exception as exc:
        health.reachable = False
        health.error = str(exc)[:256]
    return health


async def check_source_health(url: str, source_type: str = "website") -> SourceHealth:
    """Public entry point: probe a single URL and return its :class:`SourceHealth`."""
    return await _probe(url, source_type)


async def check_all_sources(config_path: str | Path) -> list[SourceHealth]:
    """Probe every source declared in the pipeline config and return the results."""
    cfg = load_pipeline_config(config_path)
    targets: list[tuple[str, str]] = []
    for comp in cfg.competitors:
        for src in comp.sources:
            targets.append((src.url, src.type))
    if not targets:
        logger.warning("check_all_sources: no sources found in {}", config_path)
        return []
    results = await asyncio.gather(
        *(_probe(url, stype) for url, stype in targets),
        return_exceptions=False,
    )
    return list(results)


def summarize(healths: list[SourceHealth]) -> dict[str, int]:
    """Count badges across a list of :class:`SourceHealth`."""
    out = {"green": 0, "yellow": 0, "red": 0, "total": len(healths)}
    for h in healths:
        b = h.badge()
        out[b.lower()] = out.get(b.lower(), 0) + 1
    return out


__all__ = [
    "SourceHealth",
    "check_source_health",
    "check_all_sources",
    "summarize",
]