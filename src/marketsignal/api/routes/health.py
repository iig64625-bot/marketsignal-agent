"""Health and readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from marketsignal.api.deps import get_db

router = APIRouter(tags=["health"])

VERSION = "0.1.0"


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe: returns 200 whenever the process is up."""
    return {"status": "ok", "version": VERSION}


@router.get("/ready")
def ready(session: Session = Depends(get_db)) -> dict[str, object]:
    """Readiness probe: confirms DB and (optionally) Chroma are reachable."""
    checks: dict[str, str] = {}
    try:
        session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"
    try:
        from marketsignal.rag.vector_store import VectorStore

        VectorStore()
        checks["vector_store"] = "ok"
    except Exception as exc:  # noqa: BLE001
        # Vector store is optional in dev; only mark degraded, not down.
        checks["vector_store"] = f"degraded: {exc}"
    healthy = checks.get("database", "").startswith("ok")
    return {"status": "ready" if healthy else "degraded", "checks": checks}


__all__ = ["router"]
