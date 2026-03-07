"""SQLAlchemy model for structured judgment sections.

Stores decomposed judgment sections (Facts, Issues, Arguments, Holdings,
Reasoning, Order) for section-aware search and targeted retrieval.
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class CaseSection(UUIDPrimaryKeyMixin, Base):
    """One row per structural section of a judgment."""

    __tablename__ = "case_sections"

    case_id: Mapped[str] = mapped_column(
        String, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    section_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_case_sections_case_type", "case_id", "section_type"),
        Index("ix_case_sections_case_id", "case_id"),
    )
