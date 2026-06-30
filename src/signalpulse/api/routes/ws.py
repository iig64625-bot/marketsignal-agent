"""WebSocket streaming endpoint for live pipeline progress.

The client connects to ``ws://host/ws/runs/{run_id}`` and receives a
stream of JSON events:

* ``{"type": "snapshot", "trace": {...}}`` - sent once on connect, the
  current trace JSON (if the run has any history).
* ``{"type": "node", "span": {...}}`` - sent whenever a new node span
  has completed (status is "ok" or "error").
* ``{"type": "status", "status": "completed"|"failed"|"running",
  "error_message": "..."}`` - sent when the crawl run's status changes
  in the DB. The connection closes after a final "completed" or
  "failed" status is sent.
* ``{"type": "heartbeat"}`` - sent every 15 s when no real updates
  are pending, so the connection survives idle proxy timeouts.

The server side polls the trace file (cheap, no in-memory pub/sub
needed) and the crawl_runs table. The cadence is 500 ms when
something is happening, 5 s when idle.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from sqlalchemy import select

from signalpulse.db.engine import get_engine
from signalpulse.models.crawl_run import CrawlRun
from signalpulse.utils.tracing import TRACE_DIR, load_trace

router = APIRouter(tags=["ws"])


_POLL_FAST = 0.5  # seconds
_POLL_SLOW = 5.0  # seconds
_HEARTBEAT_AFTER = 15.0  # seconds of idle before sending heartbeat


async def _read_run_status(run_id: str) -> tuple[str, str | None]:
    """Return (status, error_message) for the crawl run, or ('unknown', None)."""
    try:
        from sqlalchemy.orm import Session

        with Session(get_engine(), future=True) as s:
            row = s.execute(select(CrawlRun).where(CrawlRun.id == run_id)).scalar_one_or_none()
            if row is None:
                return ("unknown", None)
            return (str(row.status or "unknown"), row.error_message)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ws: db status read failed for run_id={}: {}", run_id, exc)
        return ("unknown", str(exc))


def _trace_status(payload: dict | None) -> str | None:
    """Return the trace's top-level status field, or None if not present."""
    if not payload:
        return None
    return str(payload.get("status") or "").strip() or None


def _new_spans_since(prev: int, payload: dict) -> list[dict]:
    """Return span dicts whose index >= prev (i.e. spans not yet sent)."""
    spans = payload.get("spans", [])
    return [spans[i] for i in range(prev, len(spans)) if spans[i].get("status") in ("ok", "error")]


def _is_terminal(status: str) -> bool:
    """Return True if the run is done (no more updates are coming)."""
    return status in ("completed", "failed", "unknown")


def _resolved_status(db_status: str, trace_status: str | None) -> str:
    """Merge DB and trace statuses; trace wins when it says "completed" or "failed".

    The DB can lag behind the trace (e.g. a run that was just finished
    in the trace but whose DB row has not been updated yet), so the
    trace's status is treated as authoritative when present.
    """
    if trace_status in ("completed", "failed"):
        return trace_status
    return db_status


@router.websocket("/ws/runs/{run_id}")
async def stream_run(ws: WebSocket, run_id: str) -> None:
    """Stream pipeline progress for ``run_id`` until the run finishes."""
    await ws.accept()
    last_status = "unknown"
    last_error: str | None = None
    sent_spans = 0
    last_activity = asyncio.get_event_loop().time()
    try:
        # Initial snapshot
        payload = load_trace(run_id)
        if payload is not None:
            sent_spans = len([s for s in payload.get("spans", []) if s.get("status") in ("ok", "error")])
            await ws.send_json({"type": "snapshot", "trace": payload})
            last_activity = asyncio.get_event_loop().time()
        # Run-status snapshot
        db_st, err = await _read_run_status(run_id)
        last_status = _resolved_status(db_st, _trace_status(payload))
        last_error = err
        await ws.send_json({"type": "status", "status": last_status, "error_message": err})
        last_activity = asyncio.get_event_loop().time()

        # Fast-path: if the run is already terminal, send done and exit.
        if _is_terminal(last_status):
            await ws.send_json({"type": "done", "status": last_status})
            return

        # Stream loop
        while True:
            await asyncio.sleep(_POLL_FAST if last_status == "running" else _POLL_SLOW)
            now = asyncio.get_event_loop().time()

            # 1) New spans
            payload = load_trace(run_id)
            if payload is not None:
                new_spans = _new_spans_since(sent_spans, payload)
                for sp in new_spans:
                    await ws.send_json({"type": "node", "span": sp})
                    sent_spans += 1
                    last_activity = now

            # 2) Status change
            db_st, err = await _read_run_status(run_id)
            new_status = _resolved_status(db_st, _trace_status(payload))
            if new_status != last_status or err != last_error:
                await ws.send_json({"type": "status", "status": new_status, "error_message": err})
                last_status = new_status
                last_error = err
                last_activity = now

            # 3) Done -> close. Check before heartbeat so terminal runs exit
            # without sending a redundant heartbeat.
            if _is_terminal(last_status):
                # Drain any final spans that may have appeared in the meantime.
                payload = load_trace(run_id)
                if payload is not None:
                    for sp in _new_spans_since(sent_spans, payload):
                        await ws.send_json({"type": "node", "span": sp})
                        sent_spans += 1
                await ws.send_json({"type": "done", "status": last_status})
                break

            # 4) Heartbeat on long idle (only if run is still ongoing).
            if now - last_activity > _HEARTBEAT_AFTER:
                await ws.send_json({"type": "heartbeat"})
                last_activity = now
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("ws: stream ended with error run_id={}: {}", run_id, exc)
        try:
            await ws.send_json({"type": "error", "detail": str(exc)[:512]})
        except Exception:  # noqa: BLE001
            pass
    finally:
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass


__all__ = ["router", "_resolved_status", "_trace_status", "_new_spans_since"]


def _ensure_trace_dir_exists() -> Path:
    """Test helper: returns the trace dir after creating it."""
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    return TRACE_DIR


def _load_trace_for_tests(run_id: str) -> dict | None:
    """Test helper: thin re-export of load_trace() so tests can monkey-patch."""
    return load_trace(run_id)


def _parse_new_spans(prev: int, payload: dict) -> list[dict]:
    """Test helper: thin re-export of _new_spans_since() so tests can unit-test it."""
    return _new_spans_since(prev, payload)
