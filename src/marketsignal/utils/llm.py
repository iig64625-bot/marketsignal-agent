"""Provider-agnostic LLM wrapper (returns a LangChain chat model)."""
from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from marketsignal.config.settings import get_settings


def get_llm(
    *,
    temperature: float = 0.2,
    model: str | None = None,
    provider: str | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """Return a chat model based on ``settings.llm_provider``.

    The supported providers are:
        - ``openai``     (default)
        - ``anthropic``
        - ``deepseek``   (OpenAI-compatible endpoint)
        - ``gemini``     (Google Generative AI)
        - ``qwen``       (Aliyun DashScope, OpenAI-compatible)
        - ``ollama``     (local LLM server, OpenAI-compatible)
        - ``custom``     (any OpenAI-compatible endpoint via LLM_BASE_URL)

    Args:
        temperature: Sampling temperature.
        model: Override the model name from settings.
        provider: Override the provider from settings.
        **kwargs: Extra kwargs passed to the underlying chat-model constructor.

    Raises:
        ValueError: If the provider is unknown.
    """
    settings = get_settings()
    chosen_provider = (provider or settings.llm_provider).lower()
    chosen_model = model or settings.llm_model

    if chosen_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set; cannot use the openai provider")
        return ChatOpenAI(
            model=chosen_model,
            temperature=temperature,
            api_key=settings.openai_api_key,
            **kwargs,
        )
    if chosen_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set; cannot use the anthropic provider")
        return ChatAnthropic(
            model=chosen_model,
            temperature=temperature,
            api_key=settings.anthropic_api_key,
            **kwargs,
        )
    if chosen_provider == "deepseek":
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set; cannot use the deepseek provider")
        return ChatOpenAI(
            model=chosen_model,
            temperature=temperature,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            **kwargs,
        )
    if chosen_provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set; cannot use the gemini provider")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise ValueError(
                "gemini provider requires langchain-google-genai; install with `pip install langchain-google-genai`"
            ) from exc
        return ChatGoogleGenerativeAI(
            model=chosen_model,
            temperature=temperature,
            google_api_key=settings.gemini_api_key,
            **kwargs,
        )
    if chosen_provider == "qwen":
        if not settings.qwen_api_key:
            raise ValueError("QWEN_API_KEY is not set; cannot use the qwen provider")
        return ChatOpenAI(
            model=chosen_model,
            temperature=temperature,
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
            **kwargs,
        )
    if chosen_provider == "ollama":
        # Ollama runs locally; no API key required, but you can pass one if your
        # reverse proxy demands it.
        return ChatOpenAI(
            model=chosen_model,
            temperature=temperature,
            api_key=settings.ollama_api_key or "ollama",
            base_url=settings.ollama_base_url,
            **kwargs,
        )
    if chosen_provider == "custom":
        if not settings.llm_base_url:
            raise ValueError("LLM_BASE_URL must be set for the custom provider")
        return ChatOpenAI(
            model=chosen_model,
            temperature=temperature,
            api_key=settings.llm_api_key or settings.openai_api_key,
            base_url=settings.llm_base_url,
            **kwargs,
        )
    raise ValueError(f"unknown LLM provider: {chosen_provider!r}")


__all__ = ["get_llm"]
