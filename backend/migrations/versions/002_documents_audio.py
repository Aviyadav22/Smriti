"""Add document analysis and audio digest tables, expand document status.

Revision ID: 002
Revises: 001
Create Date: 2026-03-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "002"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Expand documents status constraint
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status IN ('pending', 'extracting', 'analyzing', 'searching', "
        "'generating', 'completed', 'failed')",
    )

    # Add new columns to documents
    op.add_column("documents", sa.Column("processing_step", sa.String(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create document_analyses table
    op.create_table(
        "document_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("issues", JSONB(), nullable=True),
        sa.Column("parties", JSONB(), nullable=True),
        sa.Column("key_facts", sa.Text(), nullable=True),
        sa.Column("relief_sought", sa.Text(), nullable=True),
        sa.Column("counter_arguments", JSONB(), nullable=True),
        sa.Column("research_memo", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create audio_digests table
    op.create_table(
        "audio_digests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("audio_storage_path", sa.String(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="generating",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("case_id", "language", name="uq_audio_digests_case_language"),
        sa.CheckConstraint(
            "status IN ('generating', 'completed', 'failed')",
            name="ck_audio_digests_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("audio_digests")
    op.drop_table("document_analyses")

    op.drop_column("documents", "processing_completed_at")
    op.drop_column("documents", "processing_started_at")
    op.drop_column("documents", "processing_step")

    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status IN ('pending', 'processing', 'completed', 'failed')",
    )
