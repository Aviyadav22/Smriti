"""Audio digest model for case summary audio files."""

import uuid

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AudioDigest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audio_digests"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(String, nullable=False)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="generating"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("case_id", "language", name="uq_audio_digests_case_language"),
        CheckConstraint(
            "status IN ('generating', 'completed', 'failed')",
            name="ck_audio_digests_status",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AudioDigest(id={self.id}, case_id={self.case_id}, "
            f"language='{self.language}', status='{self.status}')>"
        )
