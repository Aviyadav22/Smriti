"""Add unique partial index on text_hash for DB-level dedup.

Revision ID: 033
Revises: 032
Create Date: 2026-03-21

Prevents concurrent workers from inserting duplicate rows for the same
document content. The partial index (WHERE text_hash IS NOT NULL) avoids
constraining rows that haven't been hashed yet.

Pre-step: remove any existing duplicate text_hash rows before creating
the unique index.
"""

from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove duplicate text_hash rows (keep the one with the lowest id)
    op.execute(
        """
        DELETE FROM cases a USING cases b
        WHERE a.id > b.id
          AND a.text_hash = b.text_hash
          AND a.text_hash IS NOT NULL
        """
    )

    # Create unique partial index (NOT CONCURRENTLY — inside Alembic transaction)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_cases_text_hash_unique
        ON cases (text_hash)
        WHERE text_hash IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cases_text_hash_unique")
