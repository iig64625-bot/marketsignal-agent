from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from signalpulse.models.base import Base, TimestampMixin, new_id


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_id)
    crawl_run_id: Mapped[str] = mapped_column(
        String(12), ForeignKey("crawl_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    company_id: Mapped[str | None] = mapped_column(
        String(12), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    markdown_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    json_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    claims: Mapped[list[Claim]] = relationship(  # noqa: F821
        "Claim", back_populates="report", cascade="all, delete-orphan", passive_deletes=True
    )
    citations: Mapped[list[Citation]] = relationship(  # noqa: F821
        "Citation", back_populates="report", cascade="all, delete-orphan", passive_deletes=True
    )
