from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from marketsignal.models.base import Base, TimestampMixin, new_id


class Claim(Base, TimestampMixin):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_id)
    report_id: Mapped[str] = mapped_column(
        String(12), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False, default="fact")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    is_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supporting_citation_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    report: Mapped[Report] = relationship(  # noqa: F821
        "Report", back_populates="claims", passive_deletes=True
    )
