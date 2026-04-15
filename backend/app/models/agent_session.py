"""Agent session and message models for conversation history."""

import uuid

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default="New Research Session"
    )

    messages: Mapped[list["AgentMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    executions: Mapped[list["AgentExecution"]] = relationship(  # noqa: F821
        back_populates="session",
    )

    __table_args__ = (
        CheckConstraint(
            "agent_type IN ('research', 'case_prep', 'strategy', 'drafting')",
            name="ck_agent_sessions_agent_type",
        ),
        Index("ix_agent_sessions_user_type", "user_id", "agent_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentSession(id={self.id}, agent_type='{self.agent_type}', "
            f"title='{self.title}')>"
        )


class AgentMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="query")
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session: Mapped["AgentSession"] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_agent_messages_role",
        ),
        CheckConstraint(
            "message_type IN ('query', 'memo', 'follow_up', 'follow_up_response')",
            name="ck_agent_messages_message_type",
        ),
        Index(
            "ix_agent_messages_session_created",
            "session_id",
            sa.text("created_at DESC"),
        ),
    )

    def __repr__(self) -> str:
        return f"<AgentMessage(id={self.id}, role='{self.role}', " f"type='{self.message_type}')>"
