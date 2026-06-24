"""Citation coverage: fraction of claims that are supported."""
from __future__ import annotations

from signalpulse.models.claim import Claim


def citation_coverage(claims: list[Claim]) -> float:
    if not claims:
        return 1.0
    supported = sum(1 for c in claims if c.is_supported)
    return supported / len(claims)
