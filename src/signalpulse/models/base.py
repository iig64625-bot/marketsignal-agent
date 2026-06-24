from __future__ import annotations

import datetime as _dt
import uuid

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    """Return a 12-character hex id used for every primary key."""
    return uuid.uuid4().hex[:12]


def utcnow() -> _dt.datetime:
    """Return the current UTC time (timezone-aware)."""
    return _dt.datetime.now(_dt.timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class TimestampMixin:
    """Adds `created_at` and `updated_at` columns."""

    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        default=utcnow,
    )
    updated_at: Mapped[_dt.datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        onupdate=utcnow,
        default=utcnow,
    )
