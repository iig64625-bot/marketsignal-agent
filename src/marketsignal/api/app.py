"""FastAPI application factory for the MarketSignal Agent API.

Use ``uvicorn marketsignal.api.app:create_app --factory`` to run.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from marketsignal.api.routes import health_router, reports_router, runs_router
from marketsignal.config.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks: log config and ensure DB tables exist.

    In production use Alembic; this is a dev-friendly fallback that calls
    ``Base.metadata.create_all`` on first boot.
    """
    settings = get_settings()
    logger.info(
        "MarketSignal API starting: env={} db={} llm_provider={}",
        settings.app_env,
        settings.database_url,
        settings.llm_provider,
    )
    try:
        # Ensure models are imported so metadata is populated.
        import marketsignal.models  # noqa: F401
        from marketsignal.db.engine import get_engine
        from marketsignal.models.base import Base
        Base.metadata.create_all(get_engine())
    except Exception as exc:  # noqa: BLE001
        logger.warning("lifespan: DB init failed (continuing): {}", exc)
    yield
    logger.info("MarketSignal API shutting down")


def create_app() -> FastAPI:
    """Build a configured :class:`FastAPI` instance."""
    app = FastAPI(
        title="MarketSignal Agent API",
        version="0.1.0",
        description="REST API for the MarketSignal competitive-intelligence agent.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(runs_router)
    app.include_router(reports_router)
    return app


__all__ = ["create_app"]
