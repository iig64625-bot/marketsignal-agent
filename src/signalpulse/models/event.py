from __future__ import annotations

import datetime as _dt

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from signalpulse.models.base import Base, TimestampMixin, new_id


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(
        String(12), ForeignKey("normalized_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[str] = mapped_column(
        String(12), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    published_at: Mapped[_dt.datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
