"""Chroma-backed vector store for document chunks."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import chromadb.errors
from loguru import logger

from signalpulse.config.settings import get_settings
from signalpulse.models.document_chunk import DocumentChunk
from signalpulse.rag.embedder import get_embedding_model

COLLECTION = "marketsignal_chunks"


def _persist_dir() -> Path:
    s = get_settings()
    p = Path(s.chroma_persist_dir).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


class SignalPulseVectorStore:
    """Thin wrapper around a persistent Chroma collection."""

    def __init__(self, persist_dir: str | Path | None = None) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        self._persist_dir = Path(persist_dir) if persist_dir else _persist_dir()
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self._persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Upsert chunks into the collection. Returns the number of items added."""
        if not chunks:
            return 0
        try:
            embedder = get_embedding_model()
        except ValueError as exc:
            logger.warning("embedding model unavailable: {}", exc)
            return 0
        texts = [c.chunk_text for c in chunks]
        try:
            embeddings = embedder.embed_documents(texts)
        except Exception as exc:  # noqa: BLE001
            logger.error("embedding failed: {}", exc)
            return 0
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for chunk in chunks:
            ids.append(chunk.id)
            documents.append(chunk.chunk_text)
            meta = json.loads(chunk.metadata_json) if chunk.metadata_json else {}
            meta["document_id"] = chunk.document_id
            meta["chunk_index"] = chunk.chunk_index
            metadatas.append(meta)
        self._collection.upsert(
            ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas
        )
        return len(ids)

    def search(
        self,
        query: str,
        *,
        n: int = 5,
        filter_company: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return the top-n chunks for ``query``."""
        try:
            embedder = get_embedding_model()
        except ValueError as exc:
            logger.warning("embedding model unavailable: {}", exc)
            return []
        try:
            qvec = embedder.embed_query(query)
        except Exception as exc:  # noqa: BLE001
            logger.error("query embedding failed: {}", exc)
            return []
        where: dict[str, Any] = {}
        if filter_company:
            where["company_id"] = filter_company
        kwargs: dict[str, Any] = {"query_embeddings": [qvec], "n_results": n}
        if where:
            kwargs["where"] = where
        res = self._collection.query(**kwargs)
        out: list[dict[str, Any]] = []
        for i, doc in enumerate(res.get("documents", [[]])[0]):
            meta = (res.get("metadatas", [[]])[0] or [{}])[i] if res.get("metadatas") else {}
            dist = (res.get("distances", [[]])[0] or [None])[i] if res.get("distances") else None
            out.append({"text": doc, "metadata": meta, "distance": dist})
        return out

    def reset(self) -> None:
        """Drop the entire collection (used by tests)."""
        try:
            self._client.delete_collection(COLLECTION)
        except (ValueError, chromadb.errors.ChromaError) as exc:
            logger.debug("vector_store: delete_collection failed (collection may not exist yet): {}", exc)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION, metadata={"hnsw:space": "cosine"}
        )

    @staticmethod
    def reset_persist_dir(path: str | Path | None = None) -> None:
        """Delete the on-disk Chroma store (used by tests)."""
        p = Path(path) if path else _persist_dir()
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
