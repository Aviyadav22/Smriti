"""Add agent_executions table and missing indexes.

Revision ID: 005
Revises: 004
Create Date: 2026-03-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_executions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("input_data", JSONB, nullable=True),
        sa.Column("result_data", JSONB, nullable=True),
        sa.Column("thread_id", UUID(as_uuid=True), nullable=False),
        sa.Column("current_step", sa.String(100), nullable=True),
        sa.Column("steps_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_steps", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "agent_type IN ('research', 'case_prep')",
            name="ck_agent_executions_agent_type",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'waiting_input', 'completed', 'failed', 'cancelled')",
            name="ck_agent_executions_status",
        ),
    )

    # Indexes for agent_executions
    op.create_index("ix_agent_executions_user_id", "agent_executions", ["user_id"])
    op.create_index("ix_agent_executions_status", "agent_executions", ["status"])

    # Missing indexes on existing tables
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    op.create_index("ix_documents_user_id", "documents", ["user_id"])
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_index("ix_documents_user_id", table_name="documents")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_index("ix_agent_executions_status", table_name="agent_executions")
    op.drop_index("ix_agent_executions_user_id", table_name="agent_executions")
    op.drop_table("agent_executions")
