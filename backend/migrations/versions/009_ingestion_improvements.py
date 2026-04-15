"""Ingestion improvements: new columns, CHECK constraints, FTS trigger update.

Revision ID: 009
Revises: 008
Create Date: 2026-03-10
"""

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- New columns ---
    op.add_column("cases", sa.Column("case_number", sa.String(200), nullable=True))
    op.add_column("cases", sa.Column("is_reportable", sa.Boolean(), nullable=True))
    op.add_column("cases", sa.Column("headnotes", sa.Text(), nullable=True))
    op.add_column("cases", sa.Column("outcome_summary", sa.Text(), nullable=True))
    op.add_column(
        "cases",
        sa.Column("ingestion_status", sa.String(20), nullable=False, server_default="complete"),
    )

    # --- Indexes ---
    op.create_index(
        "ix_cases_case_number",
        "cases",
        ["case_number"],
        postgresql_where=sa.text("case_number IS NOT NULL"),
    )
    op.create_index(
        "ix_cases_decision_date",
        "cases",
        ["decision_date"],
        postgresql_where=sa.text("decision_date IS NOT NULL"),
    )
    op.create_index(
        "ix_cases_s3_source_unique",
        "cases",
        ["s3_source_path"],
        unique=True,
        postgresql_where=sa.text("s3_source_path IS NOT NULL"),
    )

    # --- CHECK constraints ---
    op.create_check_constraint(
        "ck_cases_bench_type",
        "cases",
        "bench_type IN ('single','division','full','constitutional') OR bench_type IS NULL",
    )
    op.create_check_constraint(
        "ck_cases_jurisdiction",
        "cases",
        "jurisdiction IN ('civil','criminal','constitutional','tax','labor','company','family','environmental','arbitration','consumer','election','service','IP/commercial','other') OR jurisdiction IS NULL",
    )
    op.create_check_constraint(
        "ck_cases_disposal_nature",
        "cases",
        "disposal_nature IN ('Allowed','Dismissed','Partly Allowed','Withdrawn','Remanded','Disposed Of','Settled','Transferred','Modified','Other') OR disposal_nature IS NULL",
    )
    op.create_check_constraint(
        "ck_cases_ingestion_status",
        "cases",
        "ingestion_status IN ('pending','complete','vectors_failed')",
    )

    # --- Update FTS trigger to include full_text, petitioner, respondent, case_number ---
    op.execute("DROP TRIGGER IF EXISTS trigger_update_searchable_text ON cases;")
    op.execute("DROP FUNCTION IF EXISTS update_searchable_text();")
    op.execute("""
        CREATE OR REPLACE FUNCTION update_searchable_text() RETURNS TRIGGER AS $$
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
                setweight(to_tsvector('english', COALESCE(LEFT(NEW.full_text, 100000), '')), 'D');
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trigger_update_searchable_text
            BEFORE INSERT OR UPDATE ON cases
            FOR EACH ROW EXECUTE FUNCTION update_searchable_text();
    """)


def downgrade() -> None:
    # Restore original trigger
    op.execute("DROP TRIGGER IF EXISTS trigger_update_searchable_text ON cases;")
    op.execute("DROP FUNCTION IF EXISTS update_searchable_text();")
    op.execute("""
        CREATE OR REPLACE FUNCTION update_searchable_text() RETURNS TRIGGER AS $$
        BEGIN
            NEW.searchable_text :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.citation, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.court, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.judge, ' '), '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.petitioner, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.respondent, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(NEW.ratio_decidendi, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.keywords, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.acts_cited, ' '), '')), 'D');
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trigger_update_searchable_text
            BEFORE INSERT OR UPDATE ON cases
            FOR EACH ROW EXECUTE FUNCTION update_searchable_text();
    """)

    op.drop_constraint("ck_cases_ingestion_status", "cases")
    op.drop_constraint("ck_cases_disposal_nature", "cases")
    op.drop_constraint("ck_cases_jurisdiction", "cases")
    op.drop_constraint("ck_cases_bench_type", "cases")
    op.drop_index("ix_cases_s3_source_unique", "cases")
    op.drop_index("ix_cases_decision_date", "cases")
    op.drop_index("ix_cases_case_number", "cases")
    op.drop_column("cases", "ingestion_status")
    op.drop_column("cases", "outcome_summary")
    op.drop_column("cases", "headnotes")
    op.drop_column("cases", "is_reportable")
    op.drop_column("cases", "case_number")
