import pytest

from signalpulse.ingestion.health_check import SourceHealth, summarize


def test_source_health_default_badge_red():
    h = SourceHealth(url="https://x", source_type="website")
    assert h.badge() == "RED"
    assert h.reachable is False


def test_source_health_green():
    h = SourceHealth(url="https://x", source_type="website", reachable=True, status_code=200, response_time_ms=100.0)
    assert h.badge() == "GREEN"


def test_source_health_yellow_slow():
    h = SourceHealth(url="https://x", source_type="website", reachable=True, status_code=200, response_time_ms=5000.0)
    assert h.badge() == "YELLOW"


def test_source_health_red_5xx():
    h = SourceHealth(url="https://x", source_type="website", reachable=True, status_code=503, response_time_ms=50.0)
    assert h.badge() == "RED"


def test_source_health_to_dict_includes_badge():
    h = SourceHealth(url="https://x", source_type="website", reachable=True, status_code=200, response_time_ms=80.0)
    d = h.to_dict()
    assert d["badge"] == "GREEN"
    assert d["url"] == "https://x"


def test_summarize_mixed():
    hs = [
        SourceHealth(url="a", source_type="website", reachable=True, status_code=200, response_time_ms=80.0),
        SourceHealth(url="b", source_type="website", reachable=True, status_code=200, response_time_ms=5000.0),
        SourceHealth(url="c", source_type="website", reachable=False),
    ]
    s = summarize(hs)
    assert s["green"] == 1
    assert s["yellow"] == 1
    assert s["red"] == 1
    assert s["total"] == 3


def test_summarize_empty():
    assert summarize([]) == {"green": 0, "yellow": 0, "red": 0, "total": 0}


@pytest.mark.asyncio
async def test_check_source_health_unreachable():
    from signalpulse.ingestion.health_check import check_source_health
    # Port 1 should not be listening; even a 502 from a proxy still marks the source as not-reachable.
    h = await check_source_health("http://127.0.0.1:1", source_type="website")
    assert h.reachable is False