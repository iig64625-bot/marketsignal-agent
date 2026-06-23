"""Database engine factory."""
from __future__ import annotations

import sqlite3
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from marketsignal.config.settings import get_settings


def _register_sqlite_pragmas(engine: Engine) -> None:
    """Enable foreign-key enforcement for SQLite.

    SQLite does not enforce FK constraints unless ``PRAGMA foreign_keys = ON``
    is set on every new connection. We attach a connect listener that issues
    the pragma so the cascaded deletes declared on the ORM models actually
    take effect.
    """

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: sqlite3.Connection, _: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
        finally:
            cursor.close()


def get_engine() -> Engine:
    """Create a SQLAlchemy engine using the configured ``database_url``.

    The factory reads settings on every call so tests can override the
    environment and obtain a fresh engine bound to a temporary database.
    """
    settings = get_settings()
    connect_args: dict = {}
    if "sqlite" in settings.database_url:
        connect_args["check_same_thread"] = False
    engine = create_engine(
        settings.database_url,
        echo=settings.app_env == "development",
        connect_args=connect_args,
        future=True,
    )
    if engine.dialect.name == "sqlite":
        _register_sqlite_pragmas(engine)
    return engine
