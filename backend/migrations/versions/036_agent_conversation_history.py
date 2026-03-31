"""Agent conversation history: agent_sessions, agent_messages, search_history tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "036"
down_revision = "035"


def upgrade() -> None:
    # --- agent_sessions table ---
    op.create_table(
        "agent_sessions",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False, server_default="New Research Session"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "agent_type IN ('research', 'case_prep', 'strategy', 'drafting')",
            name="ck_agent_sessions_agent_type",
        ),
    )
    op.create_index("ix_agent_sessions_user_id", "agent_sessions", ["user_id"])
    op.create_index("ix_agent_sessions_user_type", "agent_sessions", ["user_id", "agent_type"])

    # --- agent_messages table ---
    op.create_table(
        "agent_messages",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "execution_id",
            UUID,
            sa.ForeignKey("agent_executions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("sources", JSONB, nullable=True),
        sa.Column("message_type", sa.String(20), nullable=False, server_default="query"),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_agent_messages_role",
        ),
        sa.CheckConstraint(
            "message_type IN ('query', 'memo', 'follow_up', 'follow_up_response')",
            name="ck_agent_messages_message_type",
        ),
    )
    op.create_index("ix_agent_messages_session_id", "agent_messages", ["session_id"])
    op.create_index(
        "ix_agent_messages_session_created",
        "agent_messages",
        ["session_id", sa.text("created_at DESC")],
    )

    # --- Add session_id to agent_executions ---
    op.add_column(
        "agent_executions",
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("agent_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_agent_executions_session_id", "agent_executions", ["session_id"])

    # --- search_history table ---
    op.create_table(
        "search_history",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("query", sa.String(2000), nullable=False),
        sa.Column("filters", JSONB, nullable=True),
        sa.Column("result_count", sa.Integer, nullable=True),
        sa.Column("is_bookmarked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_search_history_user_created", "search_history", ["user_id", sa.text("created_at DESC")])
    op.create_index(
        "ix_search_history_user_bookmarked",
        "search_history",
        ["user_id"],
        postgresql_where=sa.text("is_bookmarked = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_search_history_user_bookmarked", table_name="search_history")
    op.drop_index("ix_search_history_user_created", table_name="search_history")
    op.drop_table("search_history")

    op.drop_index("ix_agent_executions_session_id", table_name="agent_executions")
    op.drop_column("agent_executions", "session_id")

    op.drop_index("ix_agent_messages_session_created", table_name="agent_messages")
    op.drop_index("ix_agent_messages_session_id", table_name="agent_messages")
    op.drop_table("agent_messages")

    op.drop_index("ix_agent_sessions_user_type", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_user_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")
