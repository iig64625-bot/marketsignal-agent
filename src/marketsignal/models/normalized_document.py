from __future__ import annotations

import datetime as _dt

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from marketsignal.models.base import Base, TimestampMixin, new_id


class NormalizedDocument(Base, TimestampMixin):
    __tablename__ = "normalized_documents"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_id)
    raw_document_id: Mapped[str] = mapped_column(
        String(12), ForeignKey("raw_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[str] = mapped_column(
        String(12), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    clean_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    published_at: Mapped[_dt.datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    canonical_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    dedup_group: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    chunks: Mapped[list[DocumentChunk]] = relationship(  # noqa: F821
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
