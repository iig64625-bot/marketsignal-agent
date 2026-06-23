"""CLI entry point for the MarketSignal Agent pipeline."""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from loguru import logger


def main() -> int:
    parser = argparse.ArgumentParser(prog="marketsignal")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run a full pipeline")
    run.add_argument("--config", default="configs/competitors.ai-agent.yaml")
    run.add_argument(
        "--use-sample-dataset",
        action="store_true",
        help="Skip fetch / LLM steps and use the curated sample dataset (no API key needed).",
    )

    check = sub.add_parser("check-sources", help="Probe every data source in a config")
    check.add_argument("--config", default="configs/competitors.ai-agent.yaml")

    schedule_p = sub.add_parser("schedule", help="Start a cron-style scheduler that runs the pipeline")
    schedule_p.add_argument("--config", default="configs/competitors.ai-agent.yaml")
    schedule_p.add_argument("--cron", required=True, help="5-field cron expression (e.g. '*/5 * * * *')")
    schedule_p.add_argument("--name", default="marketsignal-job", help="Job name (also used as ID)")
    schedule_p.add_argument(
        "--use-sample-dataset",
        action="store_true",
        help="Run the sample pipeline (no API key required).",
    )

    args = parser.parse_args()

    if args.cmd == "run":
        logger.info(
            "Starting pipeline: config={}, sample_dataset={}",
            args.config,
            args.use_sample_dataset,
        )
        return _run_pipeline(args.config, use_sample_dataset=args.use_sample_dataset)

    if args.cmd == "check-sources":
        return _run_check_sources(args.config)

    if args.cmd == "schedule":
        return _run_schedule_command(args)

    return 1


def _run_pipeline(config_path: str, *, use_sample_dataset: bool) -> int:
    """Invoke the LangGraph pipeline. Returns process exit code."""
    from marketsignal.agents.graph import build_pipeline

    pipeline = build_pipeline(use_sample_dataset=use_sample_dataset)
    initial: dict[str, Any] = {
        "_config_path": config_path,
        "target_company": "Dify",
        "warnings": [],
        "metrics": {},
        "status": "pending",
    }
    try:
        result = asyncio.run(pipeline.ainvoke(initial))
    except Exception as exc:  # noqa: BLE001
        logger.error("pipeline failed: {}", exc)
        return 2
    status = result.get("status", "unknown")
    warnings = result.get("warnings", [])
    metrics = result.get("metrics", {})
    logger.info("Pipeline completed: status={} warnings={}", status, len(warnings))
    for w in warnings:
        logger.warning("  - {}", w)
    if metrics:
        logger.info("Metrics: {}", metrics)
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())


def _run_check_sources(config_path: str) -> int:
    """Probe every source in ``config_path`` and print a traffic-light table."""
    import asyncio

    from rich.console import Console
    from rich.table import Table

    from marketsignal.ingestion.health_check import check_all_sources, summarize

    console = Console()
    try:
        results = asyncio.run(check_all_sources(config_path))
    except Exception as exc:
        console.print(f"[red]check-sources failed: {exc}[/red]")
        return 2
    if not results:
        console.print(f"[yellow]no sources found in {config_path}[/yellow]")
        return 0
    table = Table(title=f"Source health ({config_path})")
    table.add_column("URL", style="cyan")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Time (ms)")
    table.add_column("Badge")
    badge_style = {"GREEN": "green", "YELLOW": "yellow", "RED": "red"}
    for h in results:
        table.add_row(
            h.url,
            h.source_type,
            str(h.status_code or "ERR"),
            f"{h.response_time_ms:.0f}" if h.response_time_ms is not None else "-",
            f"[{badge_style.get(h.badge(), 'white')}]{h.badge()}[/]",
        )
    console.print(table)
    summary = summarize(results)
    console.print(
        f"Summary: [green]{summary.get('green', 0)} GREEN[/], "
        f"[yellow]{summary.get('yellow', 0)} YELLOW[/], "
        f"[red]{summary.get('red', 0)} RED[/] of {summary['total']}"
    )
    return 0


def _run_schedule_command(args) -> int:
    """Subcommand: start a long-running scheduler with one or more cron jobs."""
    import time

    from rich.console import Console

    from marketsignal.scheduler import add_job, list_jobs, shutdown
    console = Console()
    add_job(
        name=args.name,
        cron=args.cron,
        config_path=args.config,
        use_sample_dataset=args.use_sample_dataset,
    )
    jobs = list_jobs()
    console.print(f"Scheduled {len(jobs)} job(s):")
    for j in jobs:
        console.print(f"  - [cyan]{j.id}[/] cron={j.cron} next_run={j.next_run}")
    console.print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("Stopping scheduler...")
        shutdown()
        return 0
