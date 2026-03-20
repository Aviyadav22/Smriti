"""Tests for Indian Kanoon API client."""
from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_response(json_data: dict) -> MagicMock:
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


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


class TestSearchEnhancements:
    """Tests for enhanced search with boolean operators, court codes, etc."""

    @pytest.mark.asyncio
    async def test_search_uses_boolean_query(self, ik_client) -> None:
        """When boolean_query is provided, it should be used instead of NL query."""
        resp = _mock_response({"docs": [{"tid": 1, "title": "Test"}]})

        with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
            await ik_client.search(
                "Section 498A",
                boolean_query="498A ANDD cruelty ANDD dowry",
            )
            call_data = mock_post.call_args[1].get("data", {})
            assert "ANDD" in call_data["formInput"]
            assert "498A" in call_data["formInput"]

    @pytest.mark.asyncio
    async def test_search_maps_court_codes(self, ik_client) -> None:
        """Court filter names should be mapped to IK doctype codes."""
        resp = _mock_response({"docs": []})

        with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
            await ik_client.search("test", court_filter="supreme_court")
            call_data = mock_post.call_args[1].get("data", {})
            assert "supremecourt" in call_data["formInput"]

    @pytest.mark.asyncio
    async def test_search_passes_date_params(self, ik_client) -> None:
        """IK date filters must be passed as fromdate/todate."""
        resp = _mock_response({"docs": []})

        with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
            await ik_client.search("test", from_date="01-01-2020", to_date="31-12-2024")
            call_data = mock_post.call_args[1].get("data", {})
            assert call_data["fromdate"] == "01-01-2020"
            assert call_data["todate"] == "31-12-2024"

    @pytest.mark.asyncio
    async def test_search_passes_sort_by(self, ik_client) -> None:
        """sort_by='mostrecent' should be passed to IK API."""
        resp = _mock_response({"docs": []})

        with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
            await ik_client.search("test", sort_by="mostrecent")
            call_data = mock_post.call_args[1].get("data", {})
            assert call_data["sortby"] == "mostrecent"

    @pytest.mark.asyncio
    async def test_search_paginates(self, ik_client) -> None:
        """max_pages > 1 should fetch multiple pages."""
        page0 = _mock_response({"docs": [{"tid": i} for i in range(10)]})
        page1 = _mock_response({"docs": [{"tid": i} for i in range(10, 15)]})

        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return page0 if call_count == 1 else page1

        with patch.object(ik_client._client, "post", side_effect=mock_post):
            results = await ik_client.search("test", max_results=15, max_pages=2)
            assert len(results) == 15
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_search_appends_title_filter(self, ik_client) -> None:
        resp = _mock_response({"docs": []})
        with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
            await ik_client.search("privacy", title_filter="Puttaswamy")
            data = mock_post.call_args[1]["data"]
            assert "title: Puttaswamy" in data["formInput"]

    @pytest.mark.asyncio
    async def test_search_appends_cite_filter(self, ik_client) -> None:
        resp = _mock_response({"docs": []})
        with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
            await ik_client.search("privacy", cite_filter="1993 AIR")
            data = mock_post.call_args[1]["data"]
            assert "cite: 1993 AIR" in data["formInput"]

    @pytest.mark.asyncio
    async def test_search_appends_author_filter(self, ik_client) -> None:
        resp = _mock_response({"docs": []})
        with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
            await ik_client.search("privacy", author_filter="chandrachud")
            data = mock_post.call_args[1]["data"]
            assert "author: chandrachud" in data["formInput"]

    @pytest.mark.asyncio
    async def test_search_appends_bench_filter(self, ik_client) -> None:
        resp = _mock_response({"docs": []})
        with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
            await ik_client.search("privacy", bench_filter="chandrachud")
            data = mock_post.call_args[1]["data"]
            assert "bench: chandrachud" in data["formInput"]

    @pytest.mark.asyncio
    async def test_search_passes_maxcites(self, ik_client) -> None:
        resp = _mock_response({"docs": []})
        with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
            await ik_client.search("privacy", max_cites=10)
            data = mock_post.call_args[1]["data"]
            assert data["maxcites"] == "10"

    def test_court_codes_mapping(self) -> None:
        """IK_COURT_CODES should have key Indian courts."""
        from app.core.providers.external.indiankanoon import IK_COURT_CODES

        assert IK_COURT_CODES["supreme_court"] == "supremecourt"
        assert IK_COURT_CODES["sc"] == "supremecourt"
        assert IK_COURT_CODES["delhi"] == "delhihighcourt"
        assert IK_COURT_CODES["bombay"] == "bombayhighcourt"
        assert len(IK_COURT_CODES) >= 10
