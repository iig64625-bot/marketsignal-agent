"""High-level RAG retrieval facade."""
from __future__ import annotations

from typing import Any

from marketsignal.rag.vector_store import MarketSignalVectorStore

_DEFAULT_STORE: MarketSignalVectorStore | None = None


def get_store() -> MarketSignalVectorStore:
    """Return a process-wide singleton :class:`MarketSignalVectorStore`."""
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = MarketSignalVectorStore()
    return _DEFAULT_STORE


def reset_store() -> None:
    """Drop the cached vector-store singleton (test helper)."""
    global _DEFAULT_STORE
    _DEFAULT_STORE = None


def retrieve_evidence(
    query: str,
    *,
    company: str | None = None,
    n: int = 5,
) -> list[dict[str, Any]]:
    """Return the top-n evidence chunks for ``query`` (optionally filtered by company)."""
    return get_store().search(query, n=n, filter_company=company)


__all__ = ["retrieve_evidence", "get_store", "reset_store"]
