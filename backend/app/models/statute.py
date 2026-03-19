"""Statute model for Indian legislative provisions."""

from datetime import date

from sqlalchemy import Boolean, Date, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Statute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "statutes"

    act_name: Mapped[str] = mapped_column(String(200), nullable=False)
    act_short_name: Mapped[str] = mapped_column(String(50), nullable=False)
    act_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    act_year: Mapped[int] = mapped_column(Integer, nullable=False)
    part: Mapped[str | None] = mapped_column(String(100), nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(100), nullable=True)
    section_number: Mapped[str] = mapped_column(String(20), nullable=False)
    section_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    section_text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_repealed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    replaced_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    replaces: Mapped[str | None] = mapped_column(String(200), nullable=True)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)
    searchable_text: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "act_short_name", "section_number", name="uq_statutes_act_section"
        ),
        Index("ix_statutes_act", "act_short_name"),
        Index("ix_statutes_section", "act_short_name", "section_number"),
        Index("ix_statutes_fts", "searchable_text", postgresql_using="gin"),
        Index("ix_statutes_doc_type", "document_type"),
    )

    def __repr__(self) -> str:
        return f"<Statute(id={self.id}, act='{self.act_short_name}', section='{self.section_number}')>"
