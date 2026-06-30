"""Compare two pipeline runs and surface meaningful changes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select, func

from signalpulse.db.session import get_session
from signalpulse.models import CrawlRun, Report, Signal, Claim, Company


@dataclass
class RunDiff:
    run_a_id: str
    run_b_id: str
    started_a: datetime
    started_b: datetime
    status_a: str
    status_b: str
    signals_a: int = 0
    signals_b: int = 0
    claims_a: int = 0
    claims_b: int = 0
    per_company_a: dict = field(default_factory=dict)
    per_company_b: dict = field(default_factory=dict)
    new_claims: list = field(default_factory=list)
    removed_claims: list = field(default_factory=list)

    @property
    def delta_signals(self) -> int:
        return self.signals_b - self.signals_a

    @property
    def delta_claims(self) -> int:
        return self.claims_b - self.claims_a


def list_recent_runs(limit: int = 20) -> list:
    """Return the most recent runs (newest first)."""
    with get_session() as s:
        stmt = select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(limit)
        return list(s.execute(stmt).scalars().all())


def _company_names() -> dict:
    with get_session() as s:
        return {c.id: c.name for c in s.execute(select(Company)).scalars().all()}


def _per_company_signal_counts(crawl_run_id: str) -> dict:
    with get_session() as s:
        rows = s.execute(
            select(Company.name, func.count(Signal.id))
            .join(Signal, Signal.company_id == Company.id)
            .where(Signal.crawl_run_id == crawl_run_id)
            .group_by(Company.name)
        ).all()
        return {name: int(count) for name, count in rows}


def _claim_texts_for_run(crawl_run_id: str) -> list:
    with get_session() as s:
        return list(
            s.execute(
                select(Claim.claim_text)
                .join(Report, Claim.report_id == Report.id)
                .where(Report.crawl_run_id == crawl_run_id)
            ).scalars().all()
        )


def compute_diff(run_a_id: str, run_b_id: str) -> RunDiff:
    """Compare two runs. ``run_b`` is treated as the 'current' (newer) one."""
    with get_session() as s:
        run_a = s.get(CrawlRun, run_a_id)
        run_b = s.get(CrawlRun, run_b_id)
        if run_a is None:
            raise ValueError(f"Run not found: {run_a_id}")
        if run_b is None:
            raise ValueError(f"Run not found: {run_b_id}")

    per_company_a = _per_company_signal_counts(run_a_id)
    per_company_b = _per_company_signal_counts(run_b_id)

    claims_a = _claim_texts_for_run(run_a_id)
    claims_b = _claim_texts_for_run(run_b_id)
    set_a, set_b = set(claims_a), set(claims_b)
    new_claims = [c for c in claims_b if c not in set_a][:15]
    removed_claims = [c for c in set_a if c not in set_b][:10]

    return RunDiff(
        run_a_id=run_a_id,
        run_b_id=run_b_id,
        started_a=run_a.started_at,
        started_b=run_b.started_at,
        status_a=run_a.status or "?",
        status_b=run_b.status or "?",
        signals_a=sum(per_company_a.values()),
        signals_b=sum(per_company_b.values()),
        claims_a=len(set_a),
        claims_b=len(set_b),
        per_company_a=per_company_a,
        per_company_b=per_company_b,
        new_claims=new_claims,
        removed_claims=removed_claims,
    )


__all__ = ["RunDiff", "list_recent_runs", "compute_diff"]
