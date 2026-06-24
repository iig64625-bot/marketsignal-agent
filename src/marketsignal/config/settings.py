"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Runtime
    app_env: str = "development"
    log_level: str = "INFO"
    tz: str = "UTC"

    # Database
    database_url: str = "sqlite:///data/marketsignal.db"

    # Vector store
    chroma_persist_dir: str = "./data/chroma"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # LLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    gemini_api_key: str = ""
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str = ""
    # Generic OpenAI-compatible override (used when provider="custom")
    llm_api_key: str = ""
    llm_base_url: str = ""

    # Crawler
    http_timeout: int = 30
    http_max_retries: int = 3
    http_rate_limit_per_sec: float = 1.0
    user_agent: str = "MarketSignalAgent/0.1"

    # Report
    default_time_window_days: int = 7
    default_report_format: str = "markdown"

    # Eval targets
    citation_coverage_target: float = 0.9
    unsupported_claim_target: float = 0.1


    # HTTP / CORS
    # WARNING: never combine `cors_origins=["*"]` with `allow_credentials=True`
    # — browsers reject the response. This allowlist is the safe default for
    # local Streamlit + React dev. Override via the CORS_ORIGINS env var
    # (JSON array, e.g. '["http://localhost:8501"]').
    cors_origins: list[str] = [
        "http://localhost:8501",  # Streamlit
        "http://localhost:3000",  # next.js / react
        "http://127.0.0.1:8501",
        "http://127.0.0.1:3000",
    ]
@lru_cache
def get_settings() -> Settings:
    return Settings()