"""Tests for Tavily web search client."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_response(json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def mock_settings():
    with patch("app.core.providers.web_search.tavily.settings") as s:
        s.tavily_api_key = "test-key"
        s.web_search_timeout = 15
        yield s


@pytest.fixture
def tavily_client(mock_settings):
    from app.core.providers.web_search.tavily import TavilySearchClient

    return TavilySearchClient(api_key="test-key")


class TestTavilyEnhancements:
    """Tests for enhanced Tavily search params."""

    @pytest.mark.asyncio
    async def test_search_sends_country(self, tavily_client) -> None:
        """country param must be passed to Tavily API."""
        resp = _mock_response({"results": []})

        with patch.object(tavily_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
            await tavily_client.search("test", country="IN")
            payload = mock_post.call_args[1]["json"]
            assert payload["country"] == "IN"

    @pytest.mark.asyncio
    async def test_search_sends_time_range(self, tavily_client) -> None:
        """time_range param must be passed to Tavily API."""
        resp = _mock_response({"results": []})

        with patch.object(tavily_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
            await tavily_client.search("test", time_range="year")
            payload = mock_post.call_args[1]["json"]
            assert payload["time_range"] == "year"

    @pytest.mark.asyncio
    async def test_search_requests_raw_content(self, tavily_client) -> None:
        """include_raw_content=True should send 'markdown' and return raw_content."""
        resp = _mock_response({"results": [
            {"title": "T", "url": "u", "content": "c", "raw_content": "# Full MD", "score": 0.9}
        ]})

        with patch.object(tavily_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
            results = await tavily_client.search("test", include_raw_content=True)
            payload = mock_post.call_args[1]["json"]
            assert payload["include_raw_content"] == "markdown"
            assert results[0]["raw_content"] == "# Full MD"

    @pytest.mark.asyncio
    async def test_search_omits_raw_content_when_not_requested(self, tavily_client) -> None:
        """Without include_raw_content, results should not have raw_content key."""
        resp = _mock_response({"results": [
            {"title": "T", "url": "u", "content": "c", "score": 0.9}
        ]})

        with patch.object(tavily_client._client, "post", new_callable=AsyncMock, return_value=resp):
            results = await tavily_client.search("test")
            assert "raw_content" not in results[0]

    @pytest.mark.asyncio
    async def test_search_no_optional_params_when_none(self, tavily_client) -> None:
        """Optional params should not appear in payload when not provided."""
        resp = _mock_response({"results": []})

        with patch.object(tavily_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
            await tavily_client.search("test")
            payload = mock_post.call_args[1]["json"]
            assert "country" not in payload
            assert "time_range" not in payload
            assert "include_raw_content" not in payload

    def test_default_domains_expanded(self) -> None:
        """Default legal domains must include key Indian legal sites."""
        from app.core.providers.web_search.tavily import _DEFAULT_LEGAL_DOMAINS

        assert "indiankanoon.org" in _DEFAULT_LEGAL_DOMAINS
        assert "livelaw.in" in _DEFAULT_LEGAL_DOMAINS
        assert "latestlaws.com" in _DEFAULT_LEGAL_DOMAINS
        assert "main.sci.gov.in" in _DEFAULT_LEGAL_DOMAINS
        assert len(_DEFAULT_LEGAL_DOMAINS) >= 7

    def test_uses_settings_timeout(self, mock_settings) -> None:
        """Client should use settings.web_search_timeout."""
        mock_settings.web_search_timeout = 25
        from app.core.providers.web_search.tavily import TavilySearchClient

        client = TavilySearchClient(api_key="test-key")
        assert client._client.timeout.connect == 25 or client._client.timeout.read == 25
