"""Lazy singleton wrapper around LangChain embeddings."""
from __future__ import annotations

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from marketsignal.config.settings import get_settings


@lru_cache
def get_embedding_model() -> Embeddings:
    """Return a cached embedding model (text-embedding-3-small by default)."""
    s = get_settings()
    if not s.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required to use the default embedding model")
    return OpenAIEmbeddings(model=s.embedding_model, api_key=s.openai_api_key)


__all__ = ["get_embedding_model"]
