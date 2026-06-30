"""Lightweight pipeline tracing (no OpenTelemetry, no extra deps).

Each LangGraph node records its entry time, exit time, duration, and a
truncated input/output summary. Traces are written to
``data/traces/{run_id}.json`` so they can be diffed across runs or
visualized in a notebook.

The trace JSON is also written *incrementally* (one rewrite per completed
span) so the WebSocket stream endpoint can poll for new spans without
having to instrument the LangGraph runtime. This is a deliberate
trade-off: a few extra disk writes per run, in exchange for being able
to observe progress in real time without any in-memory pub/sub.

As of the cost-dashboard upgrade, the trace JSON also embeds a
:class:`RunMetrics` blob (per-node token usage, latency, cost) so the
metrics endpoint and the eval runner can read it without re-instrumenting
the pipeline.
"""
from __future__ import annotations

import functools
import json
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from loguru import logger

from signalpulse.observability.run_metrics import RunMetrics

T = TypeVar("T")

TRACE_DIR = Path("data/traces")

# Cap on the in-memory trace registry. When the count exceeds this, the
# oldest entries (insertion order) are evicted. 50 is enough for any
# single long-running API process to keep a useful debug window.
_MAX_ENTRIES = 50
# 24-hour TTL on the on-disk trace file. After this, ``_prune`` will
# delete the JSON file and the in-memory entry. This bounds disk
# usage in long-lived deployments.
_MAX_AGE_SECONDS = 24 * 3600

_LOCK = threading.Lock()


@dataclass
class NodeSpan:
    """A single node's trace entry."""

    node: str
    entered_at: str
    exited_at: str | None = None
    duration_ms: float | None = None
    status: str = "running"
    error: str | None = None
    input_keys: list[str] = field(default_factory=list)
    output_keys: list[str] = field(default_factory=list)


@dataclass
class PipelineTrace:
    """Top-level trace for a single ``run_id``."""

    run_id: str
    started_at: str
    finished_at: str | None = None
    spans: list[NodeSpan] = field(default_factory=list)
    status: str = "running"

    def add_span(self, span: NodeSpan) -> None:
        self.spans.append(span)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["spans"] = [asdict(s) for s in self.spans]
        return d


_CURRENT: dict[str, PipelineTrace] = {}
_METRICS: dict[str, RunMetrics] = {}


def _drop_locked(run_id: str) -> None:
    """Remove a run from both dicts and delete the on-disk trace file.

    Caller must hold ``_LOCK``.
    """
    _CURRENT.pop(run_id, None)
    _METRICS.pop(run_id, None)
    try:
        _trace_path(run_id).unlink(missing_ok=True)
    except OSError as exc:
        logger.debug("trace: cleanup of {}.json failed: {}", run_id, exc)


def _prune_locked() -> None:
    """Bound the in-memory dict size AND the on-disk trace directory.

    Two eviction policies, both applied every time we touch the dict:

    1. Age-based: anything whose ``RunMetrics.finished_at`` is older
       than :data:`_MAX_AGE_SECONDS` is dropped. Naive ISO strings are
       treated as UTC (the producer appends "Z" and we strip it).
    2. Cap-based: if we still exceed :data:`_MAX_ENTRIES`, the
       oldest entries (dict insertion order) are dropped.

    Caller must hold ``_LOCK``.
    """
    now = time.time()
    # 1) age-based eviction
    for run_id in list(_METRICS.keys()):
        rm = _METRICS.get(run_id)
        if rm is None or not rm.finished_at:
            continue
        try:
            finished_ts = (
                datetime.fromisoformat(rm.finished_at.rstrip("Z"))
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
        except ValueError:
            continue
        if now - finished_ts > _MAX_AGE_SECONDS:
            _drop_locked(run_id)
    # 2) cap-based eviction
    while len(_METRICS) > _MAX_ENTRIES:
        oldest_run_id = next(iter(_METRICS))
        _drop_locked(oldest_run_id)


def _trace_path(run_id: str) -> Path:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    return TRACE_DIR / f"{run_id}.json"


def _persist_trace(run_id: str) -> None:
    """Write the in-memory trace + metrics blob to disk (best-effort)."""
    trace = _CURRENT.get(run_id)
    metrics = _METRICS.get(run_id)
    if trace is None:
        return
    payload: dict[str, Any] = trace.to_dict()
    if metrics is not None:
        payload["metrics"] = metrics.to_dict()
    try:
        _trace_path(run_id).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("trace: persist failed for run_id={}: {}", run_id, exc)


def start_trace(run_id: str) -> PipelineTrace:
    """Begin a new :class:`PipelineTrace` for ``run_id``."""
    trace = PipelineTrace(run_id=run_id, started_at=datetime.now(timezone.utc).isoformat() + "Z")
    _CURRENT[run_id] = trace
    metrics = RunMetrics(run_id=run_id)
    metrics.started_at = trace.started_at
    _METRICS[run_id] = metrics
    with _LOCK:
        _prune_locked()
    logger.info("trace: started run_id={}", run_id)
    return trace


def get_trace(run_id: str) -> PipelineTrace | None:
    return _CURRENT.get(run_id)


def get_metrics(run_id: str) -> RunMetrics | None:
    """Return the in-memory :class:`RunMetrics` for ``run_id`` (may be None)."""
    return _METRICS.get(run_id)


def set_model(run_id: str, model: str) -> None:
    """Stamp the active model name onto the metrics blob (for cost calc)."""
    rm = _METRICS.get(run_id)
    if rm is not None:
        rm.model = model


def finish_trace(run_id: str, status: str = "completed") -> PipelineTrace | None:
    """Mark the trace as finished and write it to disk (includes metrics blob)."""
    trace = _CURRENT.get(run_id)
    if not trace:
        return None
    trace.finished_at = datetime.now(timezone.utc).isoformat() + "Z"
    trace.status = status
    metrics = _METRICS.get(run_id)
    if metrics is not None:
        metrics.finished_at = trace.finished_at
    _persist_trace(run_id)
    with _LOCK:
        _prune_locked()
    return trace


def trace_node(node_name: str) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator: record this node's latency onto the active trace + metrics.

    The trace is written to disk on every completed span so that the
    WebSocket stream endpoint can poll for new spans in real time.
    """

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(state: Any, *args: Any, **kwargs: Any) -> T:
            run_id = state.get("run_id") if isinstance(state, dict) else None
            if not run_id:
                return await fn(state, *args, **kwargs)
            trace = _CURRENT.get(run_id) or start_trace(run_id)
            span = NodeSpan(
                node=node_name,
                entered_at=datetime.now(timezone.utc).isoformat() + "Z",
                input_keys=sorted(state.keys()) if isinstance(state, dict) else [],
            )
            t0 = time.perf_counter()
            try:
                result = await fn(state, *args, **kwargs)
                span.status = "ok"
                if isinstance(result, dict):
                    span.output_keys = sorted(result.keys())
                return result
            except Exception as exc:
                span.status = "error"
                span.error = str(exc)[:512]
                raise
            finally:
                span.exited_at = datetime.now(timezone.utc).isoformat() + "Z"
                duration_ms = (time.perf_counter() - t0) * 1000.0
                span.duration_ms = duration_ms
                trace.add_span(span)
                metrics = _METRICS.get(run_id)
                if metrics is not None:
                    metrics.record_node_latency(node_name, duration_ms)
                # Persist on every span so the WebSocket can poll.
                _persist_trace(run_id)

        return wrapper

    return decorator


def load_trace(run_id: str) -> dict[str, Any] | None:
    """Read a previously-saved trace from disk and return its JSON dict (or None)."""
    path = _trace_path(run_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


__all__ = [
    "NodeSpan",
    "PipelineTrace",
    "TRACE_DIR",
    "start_trace",
    "finish_trace",
    "get_trace",
    "get_metrics",
    "set_model",
    "load_trace",
    "trace_node",
]
