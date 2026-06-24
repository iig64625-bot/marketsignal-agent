"""Crawl-run management endpoints."""
from __future__ import annotations

import asyncio
import datetime as _dt
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from signalpulse.api.deps import get_db
from signalpulse.models.base import new_id, utcnow
from signalpulse.models.crawl_run import CrawlRun
from signalpulse.models.eval_run import EvalRun

router = APIRouter(prefix="/runs", tags=["runs"])


class RunCreateRequest(BaseModel):
    """Body for ``POST /runs``."""

    config_path: str = Field(
        default="configs/competitors.ai-agent.yaml",
        description="Path to the competitor YAML config.",
    )
    use_sample_dataset: bool = Field(
        default=False,
        description="Skip fetch / LLM and use the bundled sample dataset.",
    )
    target_company: str | None = Field(
        default=None,
        description="Override the target company name (default: read from config YAML).",
    )
    triggered_by: str = Field(default="api", max_length=64)


class RunResponse(BaseModel):
    """Serialized :class:`CrawlRun` plus its eval metrics (if any)."""

    id: str
    started_at: _dt.datetime
    finished_at: _dt.datetime | None
    status: str
    triggered_by: str
    time_window_start: _dt.datetime | None
    time_window_end: _dt.datetime | None
    error_message: str | None
    metrics: dict[str, float] = Field(default_factory=dict)


def _serialize_run(run: CrawlRun, metrics: dict[str, float]) -> RunResponse:
    return RunResponse(
        id=run.id,
        started_at=run.started_at,
        finished_at=run.finished_at,
        status=run.status,
        triggered_by=run.triggered_by,
        time_window_start=run.time_window_start,
        time_window_end=run.time_window_end,
        error_message=run.error_message,
        metrics=metrics,
    )


def _latest_metrics(run_id: str, session: Session) -> dict[str, float]:
    """Return the most recent :class:`EvalRun` metrics for ``run_id`` (best-effort)."""
    row = (
        session.query(EvalRun)
        .filter_by(crawl_run_id=run_id)
        .order_by(desc(EvalRun.created_at))
        .first()
    )
    if not row:
        return {}
    out: dict[str, float] = {
        "citation_coverage": float(row.citation_coverage or 0.0),
        "unsupported_claim_rate": float(row.unsupported_claim_rate or 0.0),
        "dedup_rate": float(row.dedup_rate or 0.0),
        "avg_latency_ms": float(row.avg_latency_ms or 0.0),
        "token_cost_usd": float(row.token_cost_usd or 0.0),
    }
    return out


@router.get("", response_model=list[RunResponse])
def list_runs(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),
) -> list[RunResponse]:
    """List crawl runs in reverse-chronological order."""
    runs = (
        session.query(CrawlRun)
        .order_by(desc(CrawlRun.started_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_serialize_run(r, _latest_metrics(r.id, session)) for r in runs]


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: str, session: Session = Depends(get_db)) -> RunResponse:
    """Fetch a single run with its latest metrics."""
    run = session.get(CrawlRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    return _serialize_run(run, _latest_metrics(run_id, session))


def _execute_pipeline_async(run_id: str, config_path: str, use_sample_dataset: bool, target_company_override: str | None = None) -> None:
    """Background task: run the pipeline and persist its result.

    Runs in the FastAPI BackgroundTasks threadpool, so we can safely
    use ``asyncio.run`` to drive the (async-only) LangGraph pipeline.
    The ``target_company`` is read from the YAML config so the same
    API endpoint respects the user's competitor config.
    """
    from signalpulse.agents.graph import build_pipeline
    from signalpulse.config.loader import load_pipeline_config
    from signalpulse.db.session import get_session

    try:
        target_company = "Dify"  # safe fallback if config is unreadable
        try:
            cfg = load_pipeline_config(config_path)
            target_company = cfg.target.name
        except Exception as cfg_exc:  # noqa: BLE001
            logger.warning("runs: failed to load target_company from {}: {}", config_path, cfg_exc)
        pipeline = build_pipeline(use_sample_dataset=use_sample_dataset)
        initial: dict[str, Any] = {
            "_config_path": config_path,
            "run_id": run_id,
            "target_company": target_company,
            "warnings": [],
            "metrics": {},
            "status": "pending",
        }
        result: dict[str, Any] = asyncio.run(pipeline.ainvoke(initial))
        with get_session() as s:
            row = s.get(CrawlRun, run_id)
            if row:
                row.status = str(result.get("status", "completed"))
                row.finished_at = utcnow()
                errs = result.get("warnings") or []
                row.error_message = "\n".join(errs) if errs else None
    except Exception as exc:  # noqa: BLE001
        with get_session() as s:
            row = s.get(CrawlRun, run_id)
            if row:
                row.status = "failed"
                row.finished_at = utcnow()
                row.error_message = str(exc)[:2048]


@router.post("", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
def create_run(
    body: RunCreateRequest,
    background: BackgroundTasks,
    session: Session = Depends(get_db),
) -> RunResponse:
    """Kick off a new crawl run in the background and return the new :class:`CrawlRun`."""
    run_id = new_id()
    now = utcnow()
    window_end = now
    window_start = now - _dt.timedelta(days=7)
    run = CrawlRun(
        id=run_id,
        started_at=now,
        status="pending",
        triggered_by=body.triggered_by,
        time_window_start=window_start,
        time_window_end=window_end,
    )
    session.add(run)
    session.flush()
    background.add_task(_execute_pipeline_async, run_id, body.config_path, body.use_sample_dataset, body.target_company)
    return _serialize_run(run, {})


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(run_id: str, session: Session = Depends(get_db)) -> None:
    """Delete a crawl run and its associated eval runs."""
    run = session.get(CrawlRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    session.query(EvalRun).filter_by(crawl_run_id=run_id).delete()
    session.delete(run)
    session.flush()

__all__ = ["router", "RunResponse", "RunCreateRequest"]
