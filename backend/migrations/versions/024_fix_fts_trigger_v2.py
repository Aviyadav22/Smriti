"""Fix FTS trigger function name mismatch from migration 023.

Revision ID: 024
Revises: 023
Create Date: 2026-03-21

Migration 023 created a new function `update_searchable_text()` but the
active trigger `cases_searchable_text_trigger` calls
`cases_searchable_text_update()` (set in migration 014). The V2 fields
(operative_order, legal_principles_applied, issue_classification) were
never being indexed for full-text search.

This migration updates the CORRECT function name so the trigger fires
with V2 field support.
"""

from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the orphaned function created by 023 (never used by the trigger)
    op.execute("DROP FUNCTION IF EXISTS update_searchable_text()")

    # Recreate the CORRECT function name that the trigger references
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


def downgrade() -> None:
    # Restore pre-V2 function (without operative_order, legal_principles, issue_classification)
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
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.keywords, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.acts_cited, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(left(NEW.full_text, 100000), '')), 'D');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
