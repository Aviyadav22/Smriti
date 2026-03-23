"""Model for case-statute interpretation cross-reference."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class CaseStatuteInterpretation(UUIDPrimaryKeyMixin, Base):
    """Records which statutory provisions a case substantively interprets."""

    __tablename__ = "case_statute_interpretations"
    __table_args__ = (
        UniqueConstraint("case_id", "normalized_section", name="uq_case_statute_interp"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_text: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_section: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    act_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    interpretation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary_holding: Mapped[bool] = mapped_column(Boolean, server_default="false")
