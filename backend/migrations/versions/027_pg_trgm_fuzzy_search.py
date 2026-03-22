"""Add pg_trgm extension and trigram index on cases.title for fuzzy search.

Revision ID: 027
Revises: 026
Create Date: 2026-03-21

Enables fuzzy name matching in named_case_worker — e.g., "Keshavananda Bharti"
(misspelled) finds "Kesavananda Bharati" via trigram similarity.
"""
from alembic import op

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cases_title_trgm "
        "ON cases USING gin (title gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cases_title_trgm")
    # Don't drop extension — may be used by other indexes
