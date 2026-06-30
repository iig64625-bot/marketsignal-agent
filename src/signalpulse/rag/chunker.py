"""Token-aware sliding-window chunker for RAG indexing."""
from __future__ import annotations

import json
from typing import Any

import tiktoken

from signalpulse.models.base import new_id
from signalpulse.models.document_chunk import DocumentChunk
from signalpulse.models.normalized_document import NormalizedDocument

_ENC = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_ENC.encode(text or ""))


def chunk_document(
    doc: NormalizedDocument,
    *,
    max_tokens: int = 500,
    overlap: int = 50,
) -> list[DocumentChunk]:
    """Split ``doc.clean_text`` into overlapping token-bounded chunks.

    Each returned :class:`DocumentChunk` is unsaved; the caller persists them.
    """
    text = doc.clean_text or ""
    if not text:
        return []
    if _count_tokens(text) <= max_tokens:
        return [
            DocumentChunk(
                id=new_id(),
                document_id=doc.id,
                chunk_index=0,
                chunk_text=text,
                token_count=_count_tokens(text),
                metadata_json=json.dumps(_metadata_for(doc)),
            )
        ]
    chunks: list[DocumentChunk] = []
    # token-level sliding window
    tokens = _ENC.encode(text)
    start = 0
    idx = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_text = _ENC.decode(tokens[start:end])
        chunks.append(
            DocumentChunk(
                id=new_id(),
                document_id=doc.id,
                chunk_index=idx,
                chunk_text=chunk_text,
                token_count=end - start,
                metadata_json=json.dumps(_metadata_for(doc)),
            )
        )
        if end >= len(tokens):
            break
        start = end - overlap
        idx += 1
    return chunks


def _metadata_for(doc: NormalizedDocument) -> dict[str, Any]:
    return {
        "company_id": doc.company_id,
        "source_type": doc.source_type,
        "url": doc.canonical_url or "",
        "published_at": doc.published_at.isoformat() if doc.published_at else None,
        "document_id": doc.id,
        "title": doc.title,
    }
