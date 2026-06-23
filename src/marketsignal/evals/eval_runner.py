"""Comprehensive eval runner.

Collects every available metric for a given run_id and persists both a new
:class:`EvalRun` row and a JSON report under ``data/evals/``.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from marketsignal.evals.citation_coverage import citation_coverage
from marketsignal.evals.dedup_rate import dedup_rate
from marketsignal.evals.unsupported_claims import unsupported_claim_rate
from marketsignal.models.claim import Claim
from marketsignal.models.eval_run import EvalRun
from marketsignal.models.normalized_document import NormalizedDocument
from marketsignal.utils.tracing import TRACE_DIR


@dataclass
class EvalReport:
    """Bundle of all eval metrics for a single run."""

    run_id: str
    citation_coverage: float
    unsupported_claim_rate: float
    dedup_rate: float
    total_claims: int
    supported_claims: int
    total_normalized_docs: int
    unique_content_hashes: int
    node_latency_ms: dict[str, float] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_trace_latency(run_id: str) -> dict[str, float]:
    """Load node latencies from the trace JSON file for ``run_id`` (best effort)."""
    path = TRACE_DIR / f"{run_id}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, float] = {}
    for span in data.get("spans", []):
        if span.get("duration_ms") is not None:
            out[span.get("node", "?")] = float(span["duration_ms"])
    return out


def run_all_evals(run_id: str, session: Session) -> EvalReport:
    """Run every available eval metric for ``run_id`` and persist the row + JSON.

    The :class:`EvalRun` is created with the existing schema columns. Extra
    fields (latency, claims breakdown) are stored in the ``summary_json`` blob.
    """
    claims: list[Claim] = (
        session.query(Claim).join(Claim.report).filter_by(crawl_run_id=run_id).all()
    )
    docs: list[NormalizedDocument] = (
        session.query(NormalizedDocument).all()
    )
    coverage = citation_coverage(claims)
    unsup = unsupported_claim_rate(claims)
    dup = dedup_rate(docs)
    latencies = _read_trace_latency(run_id)
    report = EvalReport(
        run_id=run_id,
        citation_coverage=coverage,
        unsupported_claim_rate=unsup,
        dedup_rate=dup,
        total_claims=len(claims),
        supported_claims=sum(1 for c in claims if c.is_supported),
        total_normalized_docs=len(docs),
        unique_content_hashes=len({d.content_hash for d in docs if d.content_hash}),
        node_latency_ms=latencies,
    )
    # Persist as EvalRun row
    from marketsignal.models.base import new_id
    row = EvalRun(
        id=new_id(),
        crawl_run_id=run_id,
        citation_coverage=coverage,
        unsupported_claim_rate=unsup,
        dedup_rate=dup,
        avg_latency_ms=sum(latencies.values()) / len(latencies) if latencies else 0.0,
        token_cost_usd=0.0,
        summary_json=json.dumps(report.to_dict(), ensure_ascii=False),
    )
    session.add(row)
    # Persist JSON
    out_dir = Path("data/evals")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"eval_{run_id}.json").write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def percentile(values: Iterable[float], pct: float) -> float:
    """Return the ``pct``-th percentile (0-100) of ``values``."""
    seq = sorted(values)
    if not seq:
        return 0.0
    k = (len(seq) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(seq) - 1)
    if f == c:
        return float(seq[f])
    return float(seq[f] + (seq[c] - seq[f]) * (k - f))


__all__ = ["EvalReport", "run_all_evals", "percentile", "_read_trace_latency"]
