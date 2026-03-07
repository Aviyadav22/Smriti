"""Add case_citation_equivalents table for cross-format citation search.

Revision ID: 003
Revises: 002
Create Date: 2026-03-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_citation_equivalents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("reporter", sa.String(50), nullable=False),
        sa.Column("citation_text", sa.String(200), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.UniqueConstraint("reporter", "citation_text", name="uq_reporter_citation"),
        sa.Index("ix_citation_text", "citation_text"),
    )


def downgrade() -> None:
    op.drop_table("case_citation_equivalents")
