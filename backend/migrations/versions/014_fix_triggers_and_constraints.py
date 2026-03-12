"""Fix dual tsvector triggers, overly restrictive CHECK constraint, and missing tsvector fields.

Revision ID: 014
Revises: 013
Create Date: 2026-03-12

Issues fixed:
1. Migration 009 created trigger `trigger_update_searchable_text` with function
   `update_searchable_text()`. Migration 010 created a SECOND trigger
   `cases_searchable_text_trigger` with function `cases_searchable_text_update()`.
   Both triggers fire on INSERT/UPDATE, causing double tsvector computation.
   Fix: Drop both triggers and both functions, create a single merged trigger.

2. Migration 009 created CHECK constraint `ck_cases_ingestion_status` allowing only
   ('pending', 'complete', 'vectors_failed'). The pipeline also uses 'processing',
   'needs_review', and 'failed'. Fix: Recreate with all 6 values.

3. Migration 010's trigger lost court, judge, petitioner, respondent, keywords,
   acts_cited, description from the tsvector. The merged trigger includes ALL
   searchable fields with proper weights.
"""

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ----------------------------------------------------------------
    # 1. Fix dual triggers: drop BOTH triggers and BOTH functions
    # ----------------------------------------------------------------
    # From migration 009
    op.execute("DROP TRIGGER IF EXISTS trigger_update_searchable_text ON cases")
    op.execute("DROP FUNCTION IF EXISTS update_searchable_text()")

    # From migration 010
    op.execute("DROP TRIGGER IF EXISTS cases_searchable_text_trigger ON cases")
    op.execute("DROP FUNCTION IF EXISTS cases_searchable_text_update()")

    # Create merged trigger function with ALL fields and proper weights
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
                setweight(to_tsvector('english', COALESCE(NEW.ratio_decidendi, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.keywords, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(NEW.acts_cited, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(LEFT(NEW.full_text, 500000), '')), 'D');
            NEW.updated_at := NOW();
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    # Create single trigger
    op.execute("""
        CREATE TRIGGER cases_searchable_text_trigger
        BEFORE INSERT OR UPDATE ON cases
        FOR EACH ROW EXECUTE FUNCTION cases_searchable_text_update();
    """)

    # ----------------------------------------------------------------
    # 2. Fix CHECK constraint: add missing ingestion_status values
    # ----------------------------------------------------------------
    op.execute("ALTER TABLE cases DROP CONSTRAINT IF EXISTS ck_cases_ingestion_status")
    op.execute("""
        ALTER TABLE cases ADD CONSTRAINT ck_cases_ingestion_status
        CHECK (ingestion_status IN (
            'pending', 'processing', 'complete',
            'failed', 'vectors_failed', 'needs_review'
        ))
    """)


def downgrade() -> None:
    # ----------------------------------------------------------------
    # Restore migration 010's state (limited-field trigger)
    # ----------------------------------------------------------------
    op.execute("DROP TRIGGER IF EXISTS cases_searchable_text_trigger ON cases")
    op.execute("DROP FUNCTION IF EXISTS cases_searchable_text_update()")

    # Recreate migration 010's trigger function (limited fields, no updated_at)
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

    op.execute("""
        CREATE TRIGGER cases_searchable_text_trigger
        BEFORE INSERT OR UPDATE ON cases
        FOR EACH ROW EXECUTE FUNCTION cases_searchable_text_update();
    """)

    # Restore the original restrictive CHECK constraint from migration 009
    op.execute("ALTER TABLE cases DROP CONSTRAINT IF EXISTS ck_cases_ingestion_status")
    op.execute("""
        ALTER TABLE cases ADD CONSTRAINT ck_cases_ingestion_status
        CHECK (ingestion_status IN ('pending', 'complete', 'vectors_failed'))
    """)
