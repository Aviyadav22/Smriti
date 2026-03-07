"""Document model for user-uploaded files."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    mime_type: Mapped[str] = mapped_column(
        String, nullable=False, server_default="application/pdf"
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="pending"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_step: Mapped[str | None] = mapped_column(String, nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'extracting', 'analyzing', 'searching', "
            "'generating', 'completed', 'failed')",
            name="ck_documents_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename='{self.filename}', status='{self.status}')>"
