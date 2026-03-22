"""Fix FTS trigger regression — restore headnotes, outcome_summary, updated_at, full_text 500K.

Revision ID: 025
Revises: 024
Create Date: 2026-03-21

Migration 024 accidentally dropped headnotes and outcome_summary (weight B),
removed the updated_at := NOW() auto-update, and reduced full_text from 500K
to 100K chars. This migration restores all 17 fields with correct weights and
triggers a tsvector rebuild for all existing rows.
"""

from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Recreate function with ALL 17 fields + updated_at fix
    op.execute("""
        CREATE OR REPLACE FUNCTION cases_searchable_text_update() RETURNS trigger AS $$
        BEGIN
            NEW.searchable_text :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.citation, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.case_number, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.court, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.judge, ' '), '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.petitioner, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.respondent, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.headnotes, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.outcome_summary, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(NEW.ratio_decidendi, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(NEW.operative_order, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.keywords, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.acts_cited, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.legal_principles_applied, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.issue_classification, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(left(NEW.full_text, 500000), '')), 'D');
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Rebuild tsvectors for all existing rows by triggering a no-op UPDATE
    op.execute("UPDATE cases SET title = title;")


def downgrade() -> None:
    # Restore migration 024's function body exactly
    op.execute("""
        CREATE OR REPLACE FUNCTION cases_searchable_text_update() RETURNS trigger AS $$
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
