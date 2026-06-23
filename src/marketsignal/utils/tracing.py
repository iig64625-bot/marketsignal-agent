"""Lightweight pipeline tracing (no OpenTelemetry, no extra deps).

Each LangGraph node records its entry time, exit time, duration, and a
truncated input/output summary. Traces are written to
``data/traces/{run_id}.json`` so they can be diffed across runs or
visualized in a notebook.
"""
from __future__ import annotations

import functools
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from loguru import logger

T = TypeVar("T")

TRACE_DIR = Path("data/traces")


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


def start_trace(run_id: str) -> PipelineTrace:
    """Begin a new :class:`PipelineTrace` for ``run_id``."""
    trace = PipelineTrace(run_id=run_id, started_at=datetime.utcnow().isoformat() + "Z")
    _CURRENT[run_id] = trace
    logger.info("trace: started run_id={}", run_id)
    return trace


def get_trace(run_id: str) -> PipelineTrace | None:
    return _CURRENT.get(run_id)


def finish_trace(run_id: str, status: str = "completed") -> PipelineTrace | None:
    """Mark the trace as finished and write it to disk."""
    trace = _CURRENT.get(run_id)
    if not trace:
        return None
    trace.finished_at = datetime.utcnow().isoformat() + "Z"
    trace.status = status
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    out = TRACE_DIR / f"{run_id}.json"
    out.write_text(json.dumps(trace.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("trace: finished run_id={} status={} spans={} -> {}", run_id, status, len(trace.spans), out)
    return trace


def trace_node(node_name: str) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator: record enter/exit time and status for a LangGraph node.

    The wrapped function must accept a :class:`GraphState` whose first key is
    ``run_id``; if absent, the decorator is a no-op (useful in unit tests).
    """

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(state: dict[str, Any], *args: Any, **kwargs: Any) -> T:
            run_id = state.get("run_id") if isinstance(state, dict) else None
            if not run_id:
                return await fn(state, *args, **kwargs)
            trace = _CURRENT.get(run_id) or start_trace(run_id)
            span = NodeSpan(
                node=node_name,
                entered_at=datetime.utcnow().isoformat() + "Z",
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
                span.exited_at = datetime.utcnow().isoformat() + "Z"
                span.duration_ms = (time.perf_counter() - t0) * 1000.0
                trace.add_span(span)

        return wrapper

    return decorator


__all__ = [
    "NodeSpan",
    "PipelineTrace",
    "TRACE_DIR",
    "start_trace",
    "finish_trace",
    "get_trace",
    "trace_node",
]
