"""Report listing, retrieval, and download endpoints."""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from signalpulse.api.deps import get_db
from signalpulse.models.report import Report

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportListItem(BaseModel):
    """Summary view used by ``GET /reports``."""

    id: str
    crawl_run_id: str
    report_type: str
    company_id: str | None
    title: str
    created_at: _dt.datetime | None


class ReportDetail(ReportListItem):
    """Detailed view that also embeds the rendered Markdown body."""

    markdown: str


def _serialize_list(r: Report) -> ReportListItem:
    return ReportListItem(
        id=r.id,
        crawl_run_id=r.crawl_run_id,
        report_type=r.report_type,
        company_id=r.company_id,
        title=r.title,
        created_at=r.created_at,
    )


def _serialize_detail(r: Report) -> ReportDetail:
    body = ""
    if r.markdown_path:
        try:
            body = Path(r.markdown_path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            body = ""
    return ReportDetail(
        id=r.id,
        crawl_run_id=r.crawl_run_id,
        report_type=r.report_type,
        company_id=r.company_id,
        title=r.title,
        created_at=r.created_at,
        markdown=body,
    )


@router.get("", response_model=list[ReportListItem])
def list_reports(
    report_type: str | None = Query(default=None, description="Filter by report_type"),
    crawl_run_id: str | None = Query(default=None, description="Filter by crawl_run_id"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),
) -> list[ReportListItem]:
    """List reports, newest first."""
    q = session.query(Report).order_by(desc(Report.created_at))
    if report_type:
        q = q.filter(Report.report_type == report_type)
    if crawl_run_id:
        q = q.filter(Report.crawl_run_id == crawl_run_id)
    return [_serialize_list(r) for r in q.offset(offset).limit(limit).all()]


@router.get("/{report_id}", response_model=ReportDetail)
def get_report(report_id: str, session: Session = Depends(get_db)) -> ReportDetail:
    """Return a single report with its rendered Markdown body."""
    r = session.get(Report, report_id)
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not found")
    return _serialize_detail(r)


@router.get("/{report_id}/download")
def download_report(report_id: str, session: Session = Depends(get_db)):
    """Stream the raw Markdown file as a download."""
    r = session.get(Report, report_id)
    if not r or not r.markdown_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report file not found")
    path = Path(r.markdown_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file missing on disk")
    return FileResponse(
        path=str(path),
        media_type="text/markdown",
        filename=path.name,
    )


@router.get("/{report_id}/markdown", response_class=PlainTextResponse)
def report_markdown(report_id: str, session: Session = Depends(get_db)) -> str:
    """Return the report body as raw ``text/markdown`` (no download headers)."""
    r = session.get(Report, report_id)
    if not r or not r.markdown_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not found")
    return Path(r.markdown_path).read_text(encoding="utf-8", errors="ignore")


__all__ = ["router", "ReportListItem", "ReportDetail"]
