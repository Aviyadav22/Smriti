"""LangGraph checkpointer setup using existing PostgreSQL."""
from __future__ import annotations

from app.core.config import settings


def get_checkpointer_connection_string() -> str:
    """Build psycopg3-compatible connection string from settings.

    LangGraph's AsyncPostgresSaver uses psycopg3, which needs
    postgresql:// prefix (not postgresql+asyncpg://).
    """
    db_url = str(settings.database_url)
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return db_url
