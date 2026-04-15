"""Enterprise readiness: provenance tracking, text_hash dedup, completeness.

Adds:
- F1: metadata_provenance JSONB column on cases
- F2: extraction_confidence float column on cases
- F7: text_hash column + unique index for content dedup

Revision ID: 013
Revises: 012
Create Date: 2026-03-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # F1: metadata_provenance — tracks source of each metadata field
    # ---------------------------------------------------------------
    op.add_column(
        "cases",
        sa.Column("metadata_provenance", JSONB, nullable=True),
    )

    # ---------------------------------------------------------------
    # F2: extraction_confidence — overall LLM extraction confidence
    # ---------------------------------------------------------------
    op.add_column(
        "cases",
        sa.Column(
            "extraction_confidence",
            sa.Float(),
            nullable=True,
        ),
    )

    # ---------------------------------------------------------------
    # F7: text_hash — SHA-256 of normalized full_text for dedup
    # ---------------------------------------------------------------
    op.add_column(
        "cases",
        sa.Column("text_hash", sa.String(64), nullable=True),
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_cases_text_hash "
        "ON cases (text_hash) WHERE text_hash IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cases_text_hash")
    op.drop_column("cases", "text_hash")
    op.drop_column("cases", "extraction_confidence")
    op.drop_column("cases", "metadata_provenance")
