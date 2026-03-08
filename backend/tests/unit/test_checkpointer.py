"""Tests for LangGraph checkpointer setup."""
from unittest.mock import patch

from app.core.agents.checkpointer import (
    get_checkpointer_connection_string,
)


class TestCheckpointerConnectionString:
    def test_converts_asyncpg_prefix(self) -> None:
        with patch("app.core.agents.checkpointer.settings") as mock_settings:
            mock_settings.database_url = "postgresql+asyncpg://user:pass@host:5432/db"
            result = get_checkpointer_connection_string()
            assert result == "postgresql://user:pass@host:5432/db"

    def test_preserves_plain_postgresql_prefix(self) -> None:
        with patch("app.core.agents.checkpointer.settings") as mock_settings:
            mock_settings.database_url = "postgresql://user:pass@host:5432/db"
            result = get_checkpointer_connection_string()
            assert result == "postgresql://user:pass@host:5432/db"
