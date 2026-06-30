"""API routes package."""
from __future__ import annotations

from signalpulse.api.routes.health import router as health_router
from signalpulse.api.routes.metrics import router as metrics_router
from signalpulse.api.routes.reports import router as reports_router
from signalpulse.api.routes.runs import router as runs_router
from signalpulse.api.routes.ws import router as ws_router

__all__ = ["health_router", "metrics_router", "reports_router", "runs_router", "ws_router"]
