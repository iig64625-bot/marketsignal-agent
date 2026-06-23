"""Shared pytest fixtures."""

from __future__ import annotations

import gc
import os
import tempfile
from pathlib import Path

import pytest

from marketsignal.config.settings import get_settings
from marketsignal.db.engine import get_engine
from marketsignal.db.session import _get_factory, reset_session_factory


@pytest.fixture
def tmp_data_dir():
    """Provide a writable temp dir and set ``DATABASE_URL`` to a SQLite file inside it.

    The fixture is function-scoped so the temp dir is cleaned up after every
    test. It also clears the ``@lru_cache`` on :func:`get_settings` and disposes
    any cached SQLAlchemy engines so the SQLite file lock is released before
    Windows ``tempfile`` cleanup runs.
    """
    with tempfile.TemporaryDirectory() as d:
        Path(d).mkdir(parents=True, exist_ok=True)
        prev_db = os.environ.get("DATABASE_URL")
        prev_chroma = os.environ.get("CHROMA_PERSIST_DIR")
        os.environ["DATABASE_URL"] = f"sqlite:///{d}/test.db"
        os.environ["CHROMA_PERSIST_DIR"] = f"{d}/chroma"
        get_settings.cache_clear()
        reset_session_factory()
        try:
            yield d
        finally:
            # Force release of any cached engine connections
            factory = _get_factory()
            if factory is not None and factory.kw.get("bind") is not None:
                factory.kw["bind"].dispose()
            try:
                get_engine().dispose()
            except Exception:
                pass
            reset_session_factory()
            get_settings.cache_clear()
            gc.collect()
            if prev_db is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = prev_db
            if prev_chroma is None:
                os.environ.pop("CHROMA_PERSIST_DIR", None)
            else:
                os.environ["CHROMA_PERSIST_DIR"] = prev_chroma
