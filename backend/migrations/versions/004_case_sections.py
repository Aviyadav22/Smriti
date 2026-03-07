"""Add case_sections table for section-aware judgment search.

Revision ID: 004
Revises: 003
Create Date: 2026-03-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_sections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_type", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("section_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Index("ix_case_sections_case_type", "case_id", "section_type"),
        sa.Index("ix_case_sections_case_id", "case_id"),
    )


def downgrade() -> None:
    op.drop_table("case_sections")
