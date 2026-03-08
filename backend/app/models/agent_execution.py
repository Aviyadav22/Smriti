"""AgentExecution model for tracking LangGraph agent runs."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentType(str, enum.Enum):
    research = "research"
    case_prep = "case_prep"
    strategy = "strategy"
    drafting = "drafting"


class AgentStatus(str, enum.Enum):
    running = "running"
    waiting_input = "waiting_input"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AgentExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_executions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="running"
    )
    input_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, default=uuid.uuid4
    )
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    steps_completed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    total_steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "agent_type IN ('research', 'case_prep', 'strategy', 'drafting')",
            name="ck_agent_executions_agent_type",
        ),
        CheckConstraint(
            "status IN ('running', 'waiting_input', 'completed', 'failed', 'cancelled')",
            name="ck_agent_executions_status",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentExecution(id={self.id}, agent_type='{self.agent_type}', "
            f"status='{self.status}')>"
        )
