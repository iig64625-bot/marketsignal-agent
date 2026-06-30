"""Tests for the RSS fetcher (mocked HTTP)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from signalpulse.ingestion.fetch_rss import fetch_rss

RSS_FIXTURE = b"""<?xml version=\"1.0\"?>
<rss version=\"2.0\"><channel>
  <title>Example</title>
  <item>
    <title>First</title>
    <link>https://x.test/a</link>
    <description>Hello</description>
  </item>
  <item>
    <title>Second</title>
    <link>https://x.test/b</link>
    <description>World</description>
  </item>
</channel></rss>
"""


@pytest.mark.asyncio
async def test_fetch_rss_returns_one_doc_per_entry():
    response = httpx.Response(
        200,
        content=RSS_FIXTURE,
        request=httpx.Request("GET", "https://x.test/feed.xml"),
    )
    fake_client = AsyncMock()
    fake_client.fetch_bytes = AsyncMock(return_value=response.content)  # type: ignore[method-assign]
    docs = await fetch_rss("https://x.test/feed.xml", source_id="s", crawl_run_id="r", client=fake_client)
    assert len(docs) == 2
    assert [d.url for d in docs] == ["https://x.test/a", "https://x.test/b"]
    assert all(d.source_id == "s" for d in docs)
    assert all(d.crawl_run_id == "r" for d in docs)
