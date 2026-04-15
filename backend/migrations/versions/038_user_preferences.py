"""Add preferences JSONB column to users table.

Revision ID: 038
Revises: 037
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "038"
down_revision = "037"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("preferences", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "preferences")
