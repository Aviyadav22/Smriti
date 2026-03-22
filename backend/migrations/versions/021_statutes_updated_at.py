"""Add updated_at column to statutes table.

Revision ID: 021
Revises: 020
Create Date: 2026-03-20

Changes:
1. Add updated_at TIMESTAMPTZ column to match TimestampMixin in the model
"""

from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE statutes
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE statutes DROP COLUMN IF EXISTS updated_at")
