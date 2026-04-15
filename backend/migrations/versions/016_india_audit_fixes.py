"""Add Hindi FTS infrastructure and anonymization tracking columns.

Revision ID: 016
Revises: 015
Create Date: 2026-03-17

Changes:
1. Add hindi_searchable_text TSVECTOR column with 'simple' config trigger
2. Add GIN index on hindi_searchable_text
3. Add is_anonymized BOOLEAN column
4. Add anonymization_flags TEXT[] column
"""

from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ----------------------------------------------------------------
    # 1. Hindi FTS infrastructure (forward-looking)
    # ----------------------------------------------------------------
    op.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS " "hindi_searchable_text tsvector")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cases_hindi_searchable_text "
        "ON cases USING gin (hindi_searchable_text) "
        "WHERE hindi_searchable_text IS NOT NULL"
    )

    # Trigger: populate hindi_searchable_text only when language = 'hindi'
    op.execute("""
        CREATE OR REPLACE FUNCTION cases_hindi_searchable_update() RETURNS trigger AS $$
        BEGIN
            IF NEW.language = 'hindi' THEN
                NEW.hindi_searchable_text :=
                    setweight(to_tsvector('simple', COALESCE(NEW.title, '')), 'A') ||
                    setweight(to_tsvector('simple', COALESCE(NEW.headnotes, '')), 'B') ||
                    setweight(to_tsvector('simple', COALESCE(NEW.ratio_decidendi, '')), 'C') ||
                    setweight(to_tsvector('simple', COALESCE(LEFT(NEW.full_text, 500000), '')), 'D');
            ELSE
                NEW.hindi_searchable_text := NULL;
            END IF;
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER cases_hindi_searchable_trigger
        BEFORE INSERT OR UPDATE ON cases
        FOR EACH ROW EXECUTE FUNCTION cases_hindi_searchable_update();
    """)

    # ----------------------------------------------------------------
    # 2. Anonymization tracking columns
    # ----------------------------------------------------------------
    op.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS " "is_anonymized BOOLEAN DEFAULT FALSE")
    op.execute(
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS " "anonymization_flags TEXT[] DEFAULT '{}'"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS cases_hindi_searchable_trigger ON cases")
    op.execute("DROP FUNCTION IF EXISTS cases_hindi_searchable_update()")
    op.execute("DROP INDEX IF EXISTS idx_cases_hindi_searchable_text")
    op.execute("ALTER TABLE cases DROP COLUMN IF EXISTS hindi_searchable_text")
    op.execute("ALTER TABLE cases DROP COLUMN IF EXISTS is_anonymized")
    op.execute("ALTER TABLE cases DROP COLUMN IF EXISTS anonymization_flags")
