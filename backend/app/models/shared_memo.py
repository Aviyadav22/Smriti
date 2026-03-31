"""SharedMemo model for public memo sharing."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class SharedMemo(Base):
    __tablename__ = "shared_memos"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    execution_id = Column(UUID(as_uuid=True), ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    share_token = Column(String(32), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, server_default=text("true"), nullable=False)
    view_count = Column(Integer, server_default=text("0"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
