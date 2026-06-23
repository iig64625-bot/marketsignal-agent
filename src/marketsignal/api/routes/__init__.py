"""API routes package."""
from __future__ import annotations

from marketsignal.api.routes.health import router as health_router
from marketsignal.api.routes.metrics import router as metrics_router
from marketsignal.api.routes.reports import router as reports_router
from marketsignal.api.routes.runs import router as runs_router
from marketsignal.api.routes.ws import router as ws_router

__all__ = ["health_router", "metrics_router", "reports_router", "runs_router", "ws_router"]
