"""Lazy singleton wrapper around LangChain embeddings."""
from __future__ import annotations

from functools import lru_cache

from langchain_core.embeddings import Embeddings

from signalpulse.config.settings import get_settings


@lru_cache
def get_embedding_model() -> Embeddings:
    """Return a cached embedding model.

    - If ``settings.embedding_model`` looks like a HuggingFace repo id
      (contains ``/``), use FastEmbed (pure-ONNX, no torch, no DLL issues).
    - Otherwise, use an OpenAI-compatible embedding API, honouring
      ``settings.llm_base_url`` for proxy endpoints.
    """
    s = get_settings()
    model = s.embedding_model

    if "/" in model:
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
        return FastEmbedEmbeddings(model_name=model)

    if not s.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required to use the default embedding model")
    from langchain_openai import OpenAIEmbeddings
    kwargs: dict = {"model": model, "api_key": s.openai_api_key}
    if s.llm_base_url:
        kwargs["base_url"] = s.llm_base_url
    return OpenAIEmbeddings(**kwargs)


__all__ = ["get_embedding_model"]
