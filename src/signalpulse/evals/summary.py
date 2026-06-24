"""Eval summary builder: collects all metrics and writes an :class:`EvalRun` row."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from signalpulse.evals.citation_coverage import citation_coverage
from signalpulse.evals.dedup_rate import dedup_rate
from signalpulse.evals.unsupported_claims import unsupported_claim_rate
from signalpulse.models.base import new_id
from signalpulse.models.claim import Claim
from signalpulse.models.eval_run import EvalRun
from signalpulse.models.normalized_document import NormalizedDocument


def build_eval_summary(run_id: str, session: Session) -> EvalRun:
    """Compute every eval metric for ``run_id`` and persist a new :class:`EvalRun`."""
    claims: list[Claim] = (
        session.query(Claim).join(Claim.report).filter_by(crawl_run_id=run_id).all()
    )
    docs: list[NormalizedDocument] = (
        session.query(NormalizedDocument).filter_by().all()  # aggregate across runs for dedup_rate
    )
    coverage = citation_coverage(claims)
    unsup = unsupported_claim_rate(claims)
    dup = dedup_rate(docs)
    summary: dict[str, Any] = {
        "total_claims": len(claims),
        "supported_claims": sum(1 for c in claims if c.is_supported),
        "total_normalized_docs": len(docs),
        "unique_content_hashes": len({d.content_hash for d in docs if d.content_hash}),
    }
    row = EvalRun(
        id=new_id(),
        crawl_run_id=run_id,
        citation_coverage=coverage,
        unsupported_claim_rate=unsup,
        dedup_rate=dup,
        avg_latency_ms=0.0,
        token_cost_usd=0.0,
        summary_json=json.dumps(summary, ensure_ascii=False),
    )
    session.add(row)
    return row
