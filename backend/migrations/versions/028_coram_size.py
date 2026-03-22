"""Add coram_size column to cases table.

Revision ID: 028
Revises: 027
Create Date: 2026-03-21
"""

import sqlalchemy as sa
from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS coram_size INTEGER")


def downgrade() -> None:
    # Don't drop — migration 011 owns this column
    pass
