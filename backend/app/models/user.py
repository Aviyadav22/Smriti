"""User model for authentication and authorization."""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="researcher",
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("true")
    )
    failed_login_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preferences: Mapped[dict] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'researcher', 'viewer')",
            name="ck_users_role",
        ),
    )

    def __repr__(self) -> str:
        masked = self.email[:3] + "***" if self.email else "?"
        return f"<User(id={self.id}, email='{masked}', role='{self.role}')>"
