from unittest.mock import patch

import pytest

from signalpulse.config.settings import get_settings
from signalpulse.utils.llm import get_llm


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="unknown LLM provider"):
        get_llm(provider="not-a-real-provider")

def test_openai_requires_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        get_llm(provider="openai")

def test_anthropic_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is not set"):
        get_llm(provider="anthropic")

def test_deepseek_requires_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY is not set"):
        get_llm(provider="deepseek")

def test_qwen_uses_dashscope_base_url(monkeypatch):
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.setenv("LLM_PROVIDER", "qwen")
    monkeypatch.setenv("LLM_MODEL", "qwen-plus")
    with patch("signalpulse.utils.llm.ChatOpenAI") as mock:
        get_llm()
    kwargs = mock.call_args.kwargs
    assert kwargs["api_key"] == "test-key"
    assert kwargs["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert kwargs["model"] == "qwen-plus"

def test_ollama_uses_local_base_url(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "llama3")
    with patch("signalpulse.utils.llm.ChatOpenAI") as mock:
        get_llm()
    kwargs = mock.call_args.kwargs
    assert kwargs["base_url"] == "http://localhost:11434/v1"
    assert kwargs["model"] == "llama3"

def test_custom_uses_llm_base_url(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_BASE_URL", "https://my-llm.example.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "custom-key")
    monkeypatch.setenv("LLM_MODEL", "my-model")
    with patch("signalpulse.utils.llm.ChatOpenAI") as mock:
        get_llm()
    kwargs = mock.call_args.kwargs
    assert kwargs["base_url"] == "https://my-llm.example.com/v1"
    assert kwargs["api_key"] == "custom-key"
    assert kwargs["model"] == "my-model"

def test_custom_requires_base_url(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    with pytest.raises(ValueError, match="LLM_BASE_URL must be set"):
        get_llm()

def test_provider_override_wins(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "real-key")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("QWEN_API_KEY", "qwen-key")
    with patch("signalpulse.utils.llm.ChatOpenAI") as mock:
        get_llm(provider="qwen", model="qwen-turbo")
    kwargs = mock.call_args.kwargs
    assert kwargs["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"