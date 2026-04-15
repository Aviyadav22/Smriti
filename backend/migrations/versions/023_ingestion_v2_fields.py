"""Ingestion V2: 22 new metadata fields + page_map + enrichment_status.

Revision ID: 023
Revises: 022
Create Date: 2026-03-21

Future-proofing for Strategy Simulation, Judge Analytics V2, Document Generation.
Two-pass design: Flash extracts all at ingestion, Pro re-extracts 8 complex fields on demand.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Group A: Judge Behavior Modeling
    op.add_column("cases", sa.Column("arguments_raised", JSONB, nullable=True))
    op.add_column("cases", sa.Column("relief_granted", sa.Text, nullable=True))
    op.add_column("cases", sa.Column("relief_sought", sa.Text, nullable=True))
    op.add_column("cases", sa.Column("sentence_details", JSONB, nullable=True))
    op.add_column("cases", sa.Column("damages_awarded", JSONB, nullable=True))
    op.add_column("cases", sa.Column("judicial_tone", sa.String(30), nullable=True))
    op.add_column("cases", sa.Column("key_observations", ARRAY(sa.String), nullable=True))
    op.add_column("cases", sa.Column("hearing_count", sa.Integer, nullable=True))

    # Group B: Citation Intelligence
    op.add_column("cases", sa.Column("citation_treatments", JSONB, nullable=True))
    op.add_column("cases", sa.Column("distinguished_cases", ARRAY(sa.String), nullable=True))
    op.add_column("cases", sa.Column("overruled_cases", ARRAY(sa.String), nullable=True))
    op.add_column("cases", sa.Column("legal_principles_applied", ARRAY(sa.String), nullable=True))

    # Group C: Procedural Intelligence
    op.add_column("cases", sa.Column("procedural_history", JSONB, nullable=True))
    op.add_column("cases", sa.Column("interim_orders", ARRAY(sa.String), nullable=True))
    op.add_column("cases", sa.Column("filing_date", sa.Date, nullable=True))
    op.add_column("cases", sa.Column("urgency_indicators", ARRAY(sa.String), nullable=True))

    # Group D: Party & Case Intelligence
    op.add_column("cases", sa.Column("party_counsel", JSONB, nullable=True))
    op.add_column("cases", sa.Column("issue_classification", ARRAY(sa.String), nullable=True))
    op.add_column("cases", sa.Column("fact_pattern_tags", ARRAY(sa.String), nullable=True))

    # Group E: Output Quality
    op.add_column("cases", sa.Column("operative_order", sa.Text, nullable=True))
    op.add_column("cases", sa.Column("conditions_imposed", ARRAY(sa.String), nullable=True))
    op.add_column("cases", sa.Column("costs_awarded", JSONB, nullable=True))

    # PDF Deep-Linking
    op.add_column("cases", sa.Column("page_map", JSONB, nullable=True))

    # Enrichment Tracking
    op.add_column(
        "cases",
        sa.Column("enrichment_status", sa.String(20), nullable=False, server_default="flash_only"),
    )

    # Indexes
    op.create_index("ix_cases_judicial_tone", "cases", ["judicial_tone"])
    op.create_index("ix_cases_filing_date", "cases", ["filing_date"])
    op.create_index(
        "ix_cases_fact_pattern_tags", "cases", ["fact_pattern_tags"], postgresql_using="gin"
    )
    op.create_index(
        "ix_cases_issue_classification", "cases", ["issue_classification"], postgresql_using="gin"
    )
    op.create_index(
        "ix_cases_legal_principles", "cases", ["legal_principles_applied"], postgresql_using="gin"
    )
    op.create_index(
        "ix_cases_distinguished", "cases", ["distinguished_cases"], postgresql_using="gin"
    )
    op.create_index("ix_cases_overruled", "cases", ["overruled_cases"], postgresql_using="gin")
    op.create_index(
        "ix_cases_party_counsel",
        "cases",
        ["party_counsel"],
        postgresql_using="gin",
        postgresql_ops={"party_counsel": "jsonb_path_ops"},
    )
    op.create_index("ix_cases_enrichment_status", "cases", ["enrichment_status"])

    # Update FTS trigger to include new fields
    op.execute("""
        CREATE OR REPLACE FUNCTION update_searchable_text() RETURNS trigger AS $$
        BEGIN
            NEW.searchable_text :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.citation, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.case_number, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.court, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.judge, ' '), '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.petitioner, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.respondent, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(NEW.ratio_decidendi, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(NEW.operative_order, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.keywords, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.acts_cited, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.legal_principles_applied, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.issue_classification, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(left(NEW.full_text, 100000), '')), 'D');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    # Restore original FTS trigger (without V2 fields)
    op.execute("""
        CREATE OR REPLACE FUNCTION update_searchable_text() RETURNS trigger AS $$
        BEGIN
            NEW.searchable_text :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.citation, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.case_number, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.court, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.judge, ' '), '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.petitioner, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.respondent, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(NEW.ratio_decidendi, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.keywords, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.acts_cited, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(left(NEW.full_text, 100000), '')), 'D');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.drop_index("ix_cases_enrichment_status")
    op.drop_index("ix_cases_party_counsel")
    op.drop_index("ix_cases_overruled")
    op.drop_index("ix_cases_distinguished")
    op.drop_index("ix_cases_legal_principles")
    op.drop_index("ix_cases_issue_classification")
    op.drop_index("ix_cases_fact_pattern_tags")
    op.drop_index("ix_cases_filing_date")
    op.drop_index("ix_cases_judicial_tone")

    for col in [
        "enrichment_status",
        "page_map",
        "costs_awarded",
        "conditions_imposed",
        "operative_order",
        "fact_pattern_tags",
        "issue_classification",
        "party_counsel",
        "urgency_indicators",
        "filing_date",
        "interim_orders",
        "procedural_history",
        "legal_principles_applied",
        "overruled_cases",
        "distinguished_cases",
        "citation_treatments",
        "hearing_count",
        "key_observations",
        "judicial_tone",
        "damages_awarded",
        "sentence_details",
        "relief_sought",
        "relief_granted",
        "arguments_raised",
    ]:
        op.drop_column("cases", col)
