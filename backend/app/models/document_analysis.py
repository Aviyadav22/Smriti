"""Document analysis model for storing upload analysis results."""

import uuid

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_analyses"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    issues: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    key_facts: Mapped[str | None] = mapped_column(Text, nullable=True)
    relief_sought: Mapped[str | None] = mapped_column(Text, nullable=True)
    counter_arguments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    research_memo: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<DocumentAnalysis(id={self.id}, document_id={self.document_id})>"
