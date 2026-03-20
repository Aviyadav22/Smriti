"""Tests for Indian Kanoon API client."""
from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_settings():
    with patch("app.core.providers.external.indiankanoon.settings") as s:
        s.ik_api_token = "test-token"
        s.ik_rate_limit = 2.0
        s.web_search_timeout = 15
        yield s


@pytest.fixture
def ik_client(mock_settings):
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    return IndianKanoonClient(token="test-token")


class TestRateLimiter:
    """Tests for rate limiter safety."""

    def test_has_asyncio_lock(self, ik_client) -> None:
        """IndianKanoonClient must have an asyncio.Lock."""
        assert hasattr(ik_client, "_lock")
        assert isinstance(ik_client._lock, asyncio.Lock)

    def test_no_deprecated_get_event_loop(self, ik_client) -> None:
        """Rate limiter must not use deprecated asyncio.get_event_loop().time()."""
        source = inspect.getsource(ik_client._rate_limited_post)
        assert "get_event_loop" not in source, (
            "Must use asyncio.get_running_loop(), not deprecated get_event_loop()"
        )

    def test_uses_settings_timeout(self, mock_settings) -> None:
        """Client should use settings.web_search_timeout, not hardcoded."""
        mock_settings.web_search_timeout = 30
        from app.core.providers.external.indiankanoon import IndianKanoonClient

        client = IndianKanoonClient(token="test-token")
        assert client._client.timeout.connect == 30 or client._client.timeout.read == 30
