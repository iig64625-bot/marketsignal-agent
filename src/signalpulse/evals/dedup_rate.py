"""Dedup rate: fraction of normalized documents that were grouped by the deduper.

Following the plan: ``dedup_rate = deduped / total`` where ``deduped`` is the
count of documents that received a ``dedup_group`` (i.e. were recognized as
part of a duplicate group, whether as the survivor or as a duplicate of it).
"""
from __future__ import annotations

from signalpulse.models.normalized_document import NormalizedDocument


def dedup_rate(docs: list[NormalizedDocument]) -> float:
    if not docs:
        return 0.0
    return sum(1 for d in docs if d.dedup_group is not None) / len(docs)
