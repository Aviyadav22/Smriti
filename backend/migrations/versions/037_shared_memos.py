"""Add shared_memos table for public memo sharing.

Revision ID: 037
Revises: 036
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "037"
down_revision = "036"


def upgrade() -> None:
    op.create_table(
        "shared_memos",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True
        ),
        sa.Column(
            "execution_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("share_token", sa.String(32), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("view_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_shared_memos_token",
        "shared_memos",
        ["share_token"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index("idx_shared_memos_user", "shared_memos", ["user_id"])
    op.create_index(
        "idx_shared_memos_execution",
        "shared_memos",
        ["execution_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("idx_shared_memos_execution", table_name="shared_memos")
    op.drop_index("idx_shared_memos_user", table_name="shared_memos")
    op.drop_index("idx_shared_memos_token", table_name="shared_memos")
    op.drop_table("shared_memos")
