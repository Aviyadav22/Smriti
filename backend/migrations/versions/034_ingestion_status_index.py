"""Add index on cases.ingestion_status for fast orphan reconciliation.

Revision ID: 034
Revises: 033
Create Date: 2026-03-21

At 35K cases, the orphan reconciliation query
(WHERE ingestion_status = 'processing') would do a full table scan
without this index. Also adds a partial index for failed cases
to support retry queries.
"""

from alembic import op

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_cases_ingestion_status
        ON cases (ingestion_status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_cases_ingestion_failed
        ON cases (ingestion_status)
        WHERE ingestion_status = 'failed'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cases_ingestion_failed")
    op.execute("DROP INDEX IF EXISTS ix_cases_ingestion_status")
