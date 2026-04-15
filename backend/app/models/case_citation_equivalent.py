"""SQLAlchemy model for citation equivalence table.

Maps a single case to all its known citation formats (SCC, AIR, SCR, etc.)
enabling cross-format search and display.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class CaseCitationEquivalent(UUIDPrimaryKeyMixin, Base):
    """One row per citation format known for a case."""

    __tablename__ = "case_citation_equivalents"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reporter: Mapped[str] = mapped_column(String(50), nullable=False)
    citation_text: Mapped[str] = mapped_column(String(200), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("reporter", "citation_text", name="uq_reporter_citation"),
        Index("ix_citation_text", "citation_text"),
    )
