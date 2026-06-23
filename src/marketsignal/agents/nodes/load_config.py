"""Node: load YAML config and create Company/Source/CrawlRun rows."""
from __future__ import annotations

import datetime as _dt

from loguru import logger

from marketsignal.agents.state import GraphState
from marketsignal.config.loader import load_pipeline_config
from marketsignal.config.settings import get_settings
from marketsignal.db.session import get_session
from marketsignal.models.base import new_id
from marketsignal.models.company import Company
from marketsignal.models.crawl_run import CrawlRun
from marketsignal.models.source import Source
from marketsignal.utils.tracing import trace_node


@trace_node("load_config_node")
async def load_config_node(state: GraphState) -> GraphState:
    """Read the pipeline YAML, persist Company/Source/CrawlRun, return initial state."""
    config_path = state.get("_config_path")  # type: ignore[typeddict-item]
    if not config_path:
        # Fall back to a path embedded in env or default
        config_path = get_settings().default_time_window_days and "configs/competitors.ai-agent.yaml"
    cfg = load_pipeline_config(config_path or "configs/competitors.ai-agent.yaml")
    now = _dt.datetime.utcnow()
    run_id = new_id()
    with get_session() as s:
        run = CrawlRun(
            id=run_id,
            started_at=now,
            status="running",
            triggered_by="langgraph",
            time_window_start=now - _dt.timedelta(days=cfg.time_window_days),
            time_window_end=now,
        )
        s.add(run)
        target = s.query(Company).filter(Company.name == cfg.target.name).first()
        if target is None:
            target = Company(id=new_id(), name=cfg.target.name, website=cfg.target.website, description=cfg.target.description)
            s.add(target)
        s.flush()
        target_id = target.id
        comp_ids = [target_id]
        source_ids: list[str] = []
        for c in cfg.competitors:
            comp = s.query(Company).filter(Company.name == c.name).first()
            if comp is None:
                comp = Company(id=new_id(), name=c.name, website=c.website, description="")
                s.add(comp)
            s.flush()
            comp_ids.append(comp.id)
            for src in c.sources:
                row = Source(id=new_id(), company_id=comp.id, source_type=src.type, url=src.url)
                s.add(row)
                s.flush()
                source_ids.append(row.id)
    logger.info("load_config: run={} sources={}", run_id, len(source_ids))
    return {
        "run_id": run_id,
        "target_company": cfg.target.name,
        "competitor_ids": comp_ids,
        "source_ids": source_ids,
        "time_window_start": (now - _dt.timedelta(days=cfg.time_window_days)).isoformat(),
        "time_window_end": now.isoformat(),
        "warnings": [],
        "metrics": {},
        "status": "running",
    }
