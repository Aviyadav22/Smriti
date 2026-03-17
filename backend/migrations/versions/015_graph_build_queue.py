"""Create graph_build_queue table for async retry of failed citation graph builds.

Revision ID: 015
Revises: 014
Create Date: 2026-03-17

When Neo4j graph builds fail during ingestion (timeout, connection error), the
case is marked complete but its citation graph is missing.  This table records
those failures so a background worker can retry them later.
"""

from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "graph_build_queue",
        sa.Column("case_id", sa.String(), sa.ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("error", sa.String(500), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("graph_build_queue")
