"""Schema hardening — default fix, check constraint, missing indexes.

Revision ID: 029
Revises: 028
Create Date: 2026-03-21

Combined migration for:
- Fix ingestion_status default from 'complete' to 'pending'
- CHECK constraint on enrichment_status
- Partial index on author_judge
- Composite index on (court, decision_date DESC)
"""

from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix ingestion_status default (Step 6.4)
    op.execute("ALTER TABLE cases ALTER COLUMN ingestion_status SET DEFAULT 'pending'")

    # CHECK constraint on enrichment_status
    op.execute(
        "ALTER TABLE cases ADD CONSTRAINT ck_cases_enrichment_status "
        "CHECK (enrichment_status IN ('flash_only', 'pro_enriched', 'failed'))"
    )

    # Partial index on author_judge (non-null only)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cases_author_judge "
        "ON cases (author_judge) WHERE author_judge IS NOT NULL"
    )

    # Composite index for court + decision_date queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cases_court_decision_date "
        "ON cases (court, decision_date DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cases_court_decision_date")
    op.execute("DROP INDEX IF EXISTS ix_cases_author_judge")
    op.execute("ALTER TABLE cases DROP CONSTRAINT IF EXISTS ck_cases_enrichment_status")
    op.execute("ALTER TABLE cases ALTER COLUMN ingestion_status SET DEFAULT 'complete'")
