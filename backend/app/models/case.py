"""Case model for Indian legal cases."""

import uuid
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Case(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cases"

    title: Mapped[str] = mapped_column(String, nullable=False)
    citation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    case_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cnr: Mapped[str | None] = mapped_column(String(50), nullable=True)
    court: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    case_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bench_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    judge: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    author_judge: Mapped[str | None] = mapped_column(String(255), nullable=True)
    petitioner: Mapped[str | None] = mapped_column(String, nullable=True)
    respondent: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    disposal_nature: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    acts_cited: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    cases_cited: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    ratio_decidendi: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)
    searchable_text: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    pdf_storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    s3_source_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="aws_open_data"
    )
    language: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="english"
    )
    chunk_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default="0"
    )
    available_languages: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )

    # --- Migration 009 columns (ingestion improvements) ---
    case_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_reportable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    headnotes: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingestion_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="complete"
    )

    # --- Migration 011 columns (legal completeness) ---
    # C1: Coram size — exact number of judges on bench
    coram_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # C2: Lower court / appellate chain
    lower_court: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lower_court_case_number: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    appeal_from: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # C3: Opinion type and split tracking
    opinion_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    dissenting_judges: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    concurring_judges: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    split_ratio: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # C10: Party type classification
    petitioner_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    respondent_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_pil: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # C11: Companion cases
    companion_cases: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )

    __table_args__ = (
        CheckConstraint("year >= 1800 AND year <= 2200", name="ck_cases_year_range"),
        # Single-column indexes
        Index("ix_cases_court", "court"),
        Index("ix_cases_year", "year"),
        Index("ix_cases_case_type", "case_type"),
        Index("ix_cases_jurisdiction", "jurisdiction"),
        Index("ix_cases_bench_type", "bench_type"),
        Index("ix_cases_source", "source"),
        # Composite indexes
        Index("ix_cases_court_year", "court", "year"),
        Index("ix_cases_year_case_type", "year", "case_type"),
        Index("ix_cases_court_case_type", "court", "case_type"),
        # GIN indexes on arrays
        Index("ix_cases_keywords_gin", "keywords", postgresql_using="gin"),
        Index("ix_cases_acts_cited_gin", "acts_cited", postgresql_using="gin"),
        Index("ix_cases_cases_cited_gin", "cases_cited", postgresql_using="gin"),
        Index("ix_cases_judge_gin", "judge", postgresql_using="gin"),
        # GIN index on tsvector
        Index("ix_cases_searchable_text_gin", "searchable_text", postgresql_using="gin"),
        # Unique partial index on citation
        Index(
            "ix_cases_citation_unique",
            "citation",
            unique=True,
            postgresql_where=sa.text("citation IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Case(id={self.id}, title='{self.title}', court='{self.court}')>"
