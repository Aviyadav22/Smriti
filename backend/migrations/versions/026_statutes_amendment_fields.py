"""Add amendment_history, effective_from, effective_until to statutes table.

Revision ID: 026
Revises: 025
Create Date: 2026-03-21

Supports temporal validation: effective_from/effective_until track when a section
was in force. amendment_history stores a JSONB array of {date, description, gazette_ref}
records for tracking legislative amendments over time.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("statutes", sa.Column("amendment_history", JSONB, nullable=True))
    op.add_column("statutes", sa.Column("effective_from", sa.Date(), nullable=True))
    op.add_column("statutes", sa.Column("effective_until", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("statutes", "effective_until")
    op.drop_column("statutes", "effective_from")
    op.drop_column("statutes", "amendment_history")
