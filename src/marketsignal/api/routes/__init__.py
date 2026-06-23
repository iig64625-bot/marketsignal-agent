"""API routes package."""
from __future__ import annotations

from marketsignal.api.routes.health import router as health_router
from marketsignal.api.routes.reports import router as reports_router
from marketsignal.api.routes.runs import router as runs_router

__all__ = ["health_router", "reports_router", "runs_router"]
