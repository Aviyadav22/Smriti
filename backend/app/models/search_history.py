"""Search history model for persisting user search queries."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class SearchHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "search_history"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    query: Mapped[str] = mapped_column(String(2000), nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_bookmarked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<SearchHistory(id={self.id}, query='{self.query[:40]}...')>"
