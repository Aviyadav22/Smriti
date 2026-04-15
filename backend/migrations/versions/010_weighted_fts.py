"""Weighted full-text search and trigram indexes.

Revision ID: 010
Revises: 009
Create Date: 2026-03-11
"""

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop existing trigger and function
    op.execute("DROP TRIGGER IF EXISTS cases_searchable_text_trigger ON cases")
    op.execute("DROP FUNCTION IF EXISTS cases_searchable_text_update()")

    # 2. Create new trigger function with weighted tsvector
    op.execute("""
        CREATE OR REPLACE FUNCTION cases_searchable_text_update() RETURNS trigger AS $$
        BEGIN
            NEW.searchable_text :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.citation, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.case_number, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.headnotes, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.outcome_summary, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.ratio_decidendi, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(LEFT(NEW.full_text, 500000), '')), 'D');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    # 3. Recreate trigger
    op.execute("""
        CREATE TRIGGER cases_searchable_text_trigger
        BEFORE INSERT OR UPDATE ON cases
        FOR EACH ROW EXECUTE FUNCTION cases_searchable_text_update();
    """)

    # 4. Add trigram extension and indexes for auto-suggest (Task D3 prep)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cases_title_trgm " "ON cases USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cases_citation_trgm "
        "ON cases USING gin (citation gin_trgm_ops)"
    )


def downgrade() -> None:
    # Drop trigram indexes
    op.execute("DROP INDEX IF EXISTS idx_cases_citation_trgm")
    op.execute("DROP INDEX IF EXISTS idx_cases_title_trgm")

    # Restore simple trigger
    op.execute("DROP TRIGGER IF EXISTS cases_searchable_text_trigger ON cases")
    op.execute("DROP FUNCTION IF EXISTS cases_searchable_text_update()")

    op.execute("""
        CREATE OR REPLACE FUNCTION cases_searchable_text_update() RETURNS trigger AS $$
        BEGIN
            NEW.searchable_text :=
                to_tsvector('english', COALESCE(NEW.title, '') || ' ' ||
                COALESCE(NEW.citation, '') || ' ' ||
                COALESCE(LEFT(NEW.full_text, 100000), ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER cases_searchable_text_trigger
        BEFORE INSERT OR UPDATE ON cases
        FOR EACH ROW EXECUTE FUNCTION cases_searchable_text_update();
    """)
