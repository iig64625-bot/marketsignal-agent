"""Initialize the SignalPulse database and (optionally) load the sample dataset.

Usage:
    python scripts/init_db.py                # create tables only
    python scripts/init_db.py --with-sample  # also load events/signals from data/sample_dataset/
    python scripts/init_db.py --reset        # drop and recreate all tables (DESTRUCTIVE)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure the src/ directory is importable when running from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from loguru import logger

from signalpulse.config.settings import get_settings  # noqa: E402
from signalpulse.db.engine import get_engine  # noqa: E402
from signalpulse.db.session import get_session, reset_session_factory  # noqa: E402


def _create_all_tables() -> None:
    """Create every table declared on the ORM metadata."""
    # Import models so they are registered with the Base metadata.
    import signalpulse.models  # noqa: F401
    from signalpulse.models.base import Base

    Base.metadata.create_all(get_engine())
    logger.info("init_db: created all tables on {}", get_settings().database_url)


def _drop_all_tables() -> None:
    """Drop every table (use with caution)."""
    import signalpulse.models  # noqa: F401
    from signalpulse.models.base import Base

    Base.metadata.drop_all(get_engine())
    logger.warning("init_db: dropped all tables on {}", get_settings().database_url)


def _load_sample_dataset() -> None:
    """Insert the bundled sample events and signals so the dashboard has data."""
    from signalpulse.services.sample_loader import load_sample_dataset

    load_sample_dataset()
    logger.info("init_db: sample dataset loaded")


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the SignalPulse database.")
    parser.add_argument("--with-sample", action="store_true", help="Also load the sample dataset.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate all tables (DESTRUCTIVE).",
    )
    args = parser.parse_args()

    # Tests may have already monkey-patched settings via env vars; clear the cache so
    # we re-read DATABASE_URL from the current environment.
    get_settings.cache_clear()
    reset_session_factory()

    if args.reset:
        _drop_all_tables()
    _create_all_tables()
    if args.with_sample:
        _load_sample_dataset()
    logger.info("init_db: done")
    return 0


if __name__ == "__main__":
    sys.exit(main())