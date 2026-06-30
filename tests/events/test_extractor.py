"""Tests for the event extractor (LLM is mocked)."""

from __future__ import annotations

import datetime as _dt
from unittest.mock import AsyncMock, patch

import pytest

from signalpulse.events.extractor import extract_events
from signalpulse.models.base import new_id
from signalpulse.models.normalized_document import NormalizedDocument


def _make_doc(text: str = "Some product update text with enough content to process.") -> NormalizedDocument:
    return NormalizedDocument(
        id=new_id(),
        raw_document_id="r",
        company_id="c1",
        source_type="blog",
        title="t",
        clean_text=text,
        published_at=_dt.datetime(2025, 1, 1),
    )


@pytest.mark.asyncio
async def test_extract_events_returns_empty_for_short_text():
    """Documents under 20 chars are skipped without calling the LLM."""
    doc = NormalizedDocument(
        id=new_id(),
        raw_document_id="r",
        company_id="c1",
        source_type="blog",
        title="t",
        clean_text="hi",
    )
    with patch("signalpulse.events.extractor.get_llm") as get_llm_mock:
        get_llm_mock.assert_not_called()
        out = await extract_events(doc)
    assert out == []


@pytest.mark.asyncio
async def test_extract_events_returns_empty_when_no_api_key():
    """If no API key is configured, the extractor returns an empty list."""
    with patch("signalpulse.events.extractor.get_llm", side_effect=ValueError("no key")):
        out = await extract_events(_make_doc())
    assert out == []


@pytest.mark.asyncio
async def test_extract_events_maps_llm_output_to_event_rows():
    """A successful LLM call returns :class:`Event` ORM rows with correct fields."""
    from signalpulse.models.schemas import EventListOutput, EventOutput

    fake_structured = AsyncMock()
    fake_structured.ainvoke = AsyncMock(
        return_value=EventListOutput(
            events=[
                EventOutput(
                    event_type="product_update",
                    title="Launched v2",
                    summary="Big release",
                    confidence=0.9,
                    evidence_spans=["v2 launched today"],
                )
            ]
        )
    )
    fake_llm = AsyncMock()
    fake_llm.with_structured_output = lambda _schema: fake_structured
    with patch("signalpulse.events.extractor.get_llm", return_value=fake_llm):
        out = await extract_events(_make_doc())
    assert len(out) == 1
    ev = out[0]
    assert ev.event_type == "product_update"
    assert ev.title == "Launched v2"
    assert ev.confidence == 0.9
    assert "v2 launched today" in ev.evidence_json
