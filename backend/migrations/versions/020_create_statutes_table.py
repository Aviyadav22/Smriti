"""Create statutes table for statute/legislation storage.

Revision ID: 020
Revises: 019
Create Date: 2026-03-19

Changes:
1. Create statutes table with act, section, and FTS columns
2. Add indexes for act lookup, section lookup, FTS, and document type
3. Add FTS trigger for weighted searchable_text updates
"""

from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS statutes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            act_name VARCHAR(200) NOT NULL,
            act_short_name VARCHAR(50) NOT NULL,
            act_number VARCHAR(50),
            act_year INTEGER NOT NULL,
            part VARCHAR(100),
            chapter VARCHAR(100),
            section_number VARCHAR(20) NOT NULL,
            section_title VARCHAR(500),
            section_text TEXT NOT NULL,
            explanation TEXT,
            effective_date DATE,
            is_repealed BOOLEAN DEFAULT FALSE,
            replaced_by VARCHAR(200),
            replaces VARCHAR(200),
            document_type VARCHAR(20) NOT NULL,
            searchable_text TSVECTOR,
            created_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (act_short_name, section_number)
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_statutes_act ON statutes (act_short_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_statutes_section ON statutes (act_short_name, section_number)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_statutes_fts ON statutes USING GIN (searchable_text)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_statutes_doc_type ON statutes (document_type)")

    op.execute("""
        CREATE OR REPLACE FUNCTION statutes_searchable_text_trigger() RETURNS trigger AS $$
        BEGIN
            NEW.searchable_text :=
                setweight(to_tsvector('english', COALESCE(NEW.section_title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.section_text, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.act_name, '')), 'C');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE TRIGGER statutes_searchable_text_update
            BEFORE INSERT OR UPDATE ON statutes
            FOR EACH ROW EXECUTE FUNCTION statutes_searchable_text_trigger()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS statutes_searchable_text_update ON statutes")
    op.execute("DROP FUNCTION IF EXISTS statutes_searchable_text_trigger()")
    op.execute("DROP TABLE IF EXISTS statutes")
