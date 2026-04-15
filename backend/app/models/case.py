"""Case model for Indian legal cases."""

from datetime import date

import sqlalchemy as sa
from sqlalchemy import Boolean, CheckConstraint, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
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
    source: Mapped[str] = mapped_column(String(30), nullable=False, server_default="aws_open_data")
    language: Mapped[str] = mapped_column(String(20), nullable=False, server_default="english")
    chunk_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    available_languages: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # --- Migration 009 columns (ingestion improvements) ---
    case_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_reportable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    headnotes: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingestion_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )

    # --- Migration 010 columns ---
    cited_by_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # --- Migration 011 columns (legal completeness) ---
    # C1: Coram size — exact number of judges on bench
    coram_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # C2: Lower court / appellate chain
    lower_court: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lower_court_case_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    appeal_from: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # C3: Opinion type and split tracking
    opinion_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    dissenting_judges: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    concurring_judges: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    split_ratio: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # C10: Party type classification
    petitioner_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    respondent_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_pil: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # C11: Companion cases
    companion_cases: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # --- Migration 013 columns (enterprise readiness) ---
    # F1: Provenance tracking — which source provided each field
    metadata_provenance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # F2: Overall LLM extraction confidence score (0.0-1.0)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # F7: SHA-256 hash of normalized full_text for dedup
    text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- Migration 015 columns (India audit fixes) ---
    hindi_searchable_text: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    is_anonymized: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    anonymization_flags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # --- Migration 023 columns (Ingestion V2) ---
    # Group A: Judge Behavior Modeling
    arguments_raised: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    relief_granted: Mapped[str | None] = mapped_column(Text, nullable=True)
    relief_sought: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentence_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    damages_awarded: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    judicial_tone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    key_observations: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    hearing_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Group B: Citation Intelligence
    citation_treatments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    distinguished_cases: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    overruled_cases: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    legal_principles_applied: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Group C: Procedural Intelligence
    procedural_history: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    interim_orders: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    filing_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    urgency_indicators: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Group D: Party & Case Intelligence
    party_counsel: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    issue_classification: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    fact_pattern_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Group E: Output Quality
    operative_order: Mapped[str | None] = mapped_column(Text, nullable=True)
    conditions_imposed: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    costs_awarded: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # PDF Deep-Linking
    page_map: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Enrichment Tracking
    enrichment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="flash_only"
    )

    # --- Ingestion V3 fields ---
    source_dataset: Mapped[str | None] = mapped_column(
        String(50), server_default="aws_open_data_sc", index=True
    )
    legal_propositions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    statute_sections_interpreted: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fact_pattern_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_legal_issue: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # --- CHECK constraints ---
        CheckConstraint("year >= 1800 AND year <= 2200", name="ck_cases_year_range"),
        CheckConstraint(
            "opinion_type IN ('unanimous','majority','plurality','per_curiam') OR opinion_type IS NULL",
            name="ck_cases_opinion_type",
        ),
        CheckConstraint(
            "petitioner_type IN ('individual','government_central','government_state','PSU','company','NGO','statutory_body','other') OR petitioner_type IS NULL",
            name="ck_cases_petitioner_type",
        ),
        CheckConstraint(
            "respondent_type IN ('individual','government_central','government_state','PSU','company','NGO','statutory_body','other') OR respondent_type IS NULL",
            name="ck_cases_respondent_type",
        ),
        CheckConstraint("coram_size > 0 OR coram_size IS NULL", name="ck_cases_coram_size"),
        CheckConstraint(
            "disposal_nature IN ('Allowed','Dismissed','Partly Allowed','Withdrawn','Remanded','Disposed Of','Settled','Transferred','Modified','Other','Referred to Larger Bench','Abated','Not Pressed') OR disposal_nature IS NULL",
            name="ck_cases_disposal_nature",
        ),
        CheckConstraint(
            "jurisdiction IN ('civil','criminal','constitutional','tax','labor','company','family','environmental','arbitration','consumer','election','service','ip/commercial','other') OR jurisdiction IS NULL",
            name="ck_cases_jurisdiction",
        ),
        CheckConstraint(
            "ingestion_status IN ('pending', 'processing', 'complete', 'failed', 'vectors_failed', 'needs_review', 'rejected')",
            name="ck_cases_ingestion_status",
        ),
        CheckConstraint(
            "enrichment_status IN ('flash_only', 'pro_enriched', 'failed')",
            name="ck_cases_enrichment_status",
        ),
        # --- Single-column indexes ---
        Index("ix_cases_court", "court"),
        Index("ix_cases_year", "year"),
        Index("ix_cases_case_type", "case_type"),
        Index("ix_cases_jurisdiction", "jurisdiction"),
        Index("ix_cases_bench_type", "bench_type"),
        Index("ix_cases_source", "source"),
        Index("ix_cases_opinion_type", "opinion_type"),
        Index("ix_cases_is_pil", "is_pil"),
        Index("ix_cases_coram_size", "coram_size"),
        Index("ix_cases_decision_date", "decision_date"),
        Index("ix_cases_text_hash", "text_hash"),
        Index("ix_cases_judicial_tone", "judicial_tone"),
        Index("ix_cases_filing_date", "filing_date"),
        Index("ix_cases_enrichment_status", "enrichment_status"),
        Index("ix_cases_ingestion_status", "ingestion_status"),
        Index("ix_cases_disposal_nature", "disposal_nature"),
        # --- Composite indexes ---
        Index("ix_cases_court_year", "court", "year"),
        Index("ix_cases_year_case_type", "year", "case_type"),
        Index("ix_cases_court_case_type", "court", "case_type"),
        Index("ix_cases_court_decision_date", "court", sa.text("decision_date DESC")),
        # --- Partial indexes ---
        Index(
            "ix_cases_citation_unique",
            "citation",
            unique=True,
            postgresql_where=sa.text("citation IS NOT NULL"),
        ),
        Index(
            "ix_cases_author_judge",
            "author_judge",
            postgresql_where=sa.text("author_judge IS NOT NULL"),
        ),
        Index(
            "ix_cases_text_hash_unique",
            "text_hash",
            unique=True,
            postgresql_where=sa.text("text_hash IS NOT NULL"),
        ),
        # --- GIN indexes on arrays ---
        Index("ix_cases_keywords_gin", "keywords", postgresql_using="gin"),
        Index("ix_cases_acts_cited_gin", "acts_cited", postgresql_using="gin"),
        Index("ix_cases_cases_cited_gin", "cases_cited", postgresql_using="gin"),
        Index("ix_cases_judge_gin", "judge", postgresql_using="gin"),
        Index("ix_cases_fact_pattern_tags", "fact_pattern_tags", postgresql_using="gin"),
        Index("ix_cases_issue_classification", "issue_classification", postgresql_using="gin"),
        Index("ix_cases_legal_principles", "legal_principles_applied", postgresql_using="gin"),
        Index("ix_cases_distinguished", "distinguished_cases", postgresql_using="gin"),
        Index("ix_cases_overruled", "overruled_cases", postgresql_using="gin"),
        Index(
            "ix_cases_party_counsel",
            "party_counsel",
            postgresql_using="gin",
            postgresql_ops={"party_counsel": "jsonb_path_ops"},
        ),
        # --- GIN index on tsvector ---
        Index("ix_cases_searchable_text_gin", "searchable_text", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<Case(id={self.id}, title='{self.title}', court='{self.court}')>"
