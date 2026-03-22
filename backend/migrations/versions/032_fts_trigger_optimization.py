"""Optimize FTS trigger — remove updated_at side-effect, add UPDATE OF clause.

Revision ID: 032
Revises: 030
Create Date: 2026-03-21

The FTS trigger previously fired on ANY column update and set updated_at := NOW().
This caused unnecessary tsvector recomputes on status/count updates and broke the
audit trail for updated_at. This migration:
1. Removes updated_at := NOW() from the trigger function
2. Adds UPDATE OF clause so the trigger only fires when FTS-relevant columns change
"""

from alembic import op

revision = "032"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Replace trigger function — remove updated_at := NOW()
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
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Drop and recreate trigger with UPDATE OF clause
    op.execute("DROP TRIGGER IF EXISTS cases_searchable_text_trigger ON cases;")
    op.execute("""
        CREATE TRIGGER cases_searchable_text_trigger
            BEFORE INSERT OR UPDATE OF
                title, citation, case_number, court, judge, petitioner, respondent,
                headnotes, outcome_summary, description, ratio_decidendi,
                operative_order, keywords, acts_cited, legal_principles_applied,
                issue_classification, full_text
            ON cases
            FOR EACH ROW
            EXECUTE FUNCTION cases_searchable_text_update();
    """)


def downgrade() -> None:
    # Restore migration 025's trigger function (with updated_at := NOW())
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

    # Restore trigger without UPDATE OF clause
    op.execute("DROP TRIGGER IF EXISTS cases_searchable_text_trigger ON cases;")
    op.execute("""
        CREATE TRIGGER cases_searchable_text_trigger
            BEFORE INSERT OR UPDATE ON cases
            FOR EACH ROW
            EXECUTE FUNCTION cases_searchable_text_update();
    """)
