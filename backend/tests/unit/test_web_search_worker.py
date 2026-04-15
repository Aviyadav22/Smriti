"""Tests for web search worker — filter propagation."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


def _make_task(**overrides) -> dict:
    base = {
        "task_id": "test-web-1",
        "task_type": "web",
        "nl_query": "latest Supreme Court ruling on bail",
        "boolean_query": "",
        "named_cases": [],
        "rationale": "Recent developments",
        "filters": {},
        "priority": 2,
    }
    base.update(overrides)
    return base


@pytest.fixture
def mock_web_search():
    client = AsyncMock()
    client.search = AsyncMock(
        return_value=[
            {
                "title": "Latest SC Ruling",
                "url": "https://livelaw.in/test",
                "content": "Content",
                "score": 0.9,
            }
        ]
    )
    return client


class TestWebWorkerFilterPropagation:
    """Tests for filter propagation from research plan to Tavily."""

    @pytest.mark.asyncio
    async def test_passes_country_in(self, mock_web_search) -> None:
        """Web worker must always pass country=IN."""
        from app.core.agents.nodes.worker_nodes import web_search_worker

        state = {"task": _make_task()}
        await web_search_worker(state, mock_web_search)

        call_kwargs = mock_web_search.search.call_args[1]
        assert call_kwargs["country"] == "IN"

    @pytest.mark.asyncio
    async def test_passes_include_raw_content(self, mock_web_search) -> None:
        """Web worker must request raw markdown content."""
        from app.core.agents.nodes.worker_nodes import web_search_worker

        state = {"task": _make_task()}
        await web_search_worker(state, mock_web_search)

        call_kwargs = mock_web_search.search.call_args[1]
        assert call_kwargs["include_raw_content"] is True

    @pytest.mark.asyncio
    async def test_passes_time_range_from_filters(self, mock_web_search) -> None:
        """recency filter should be passed as time_range."""
        from app.core.agents.nodes.worker_nodes import web_search_worker

        state = {"task": _make_task(filters={"recency": "year"})}
        await web_search_worker(state, mock_web_search)

        call_kwargs = mock_web_search.search.call_args[1]
        assert call_kwargs["time_range"] == "year"

    @pytest.mark.asyncio
    async def test_passes_custom_domains(self, mock_web_search) -> None:
        """domains filter should override default include_domains."""
        from app.core.agents.nodes.worker_nodes import web_search_worker

        state = {"task": _make_task(filters={"domains": ["custom.com"]})}
        await web_search_worker(state, mock_web_search)

        call_kwargs = mock_web_search.search.call_args[1]
        assert call_kwargs["include_domains"] == ["custom.com"]

    @pytest.mark.asyncio
    async def test_prefers_raw_content_for_snippet(self, mock_web_search) -> None:
        """Snippet should prefer raw_content over content."""
        from app.core.agents.nodes.worker_nodes import web_search_worker

        mock_web_search.search = AsyncMock(
            return_value=[
                {
                    "title": "T",
                    "url": "u",
                    "content": "short",
                    "raw_content": "# Full markdown content",
                    "score": 0.9,
                }
            ]
        )
        state = {"task": _make_task()}
        result = await web_search_worker(state, mock_web_search)

        snippet = result["worker_results"][0]["results"][0]["snippet"]
        assert "Full markdown content" in snippet

    @pytest.mark.asyncio
    async def test_failure_returns_empty_not_error(self, mock_web_search) -> None:
        """Web search failure should return empty results, not crash pipeline."""
        from app.core.agents.nodes.worker_nodes import web_search_worker

        mock_web_search.search = AsyncMock(side_effect=Exception("API error"))
        state = {"task": _make_task()}
        result = await web_search_worker(state, mock_web_search)

        wr = result["worker_results"][0]
        assert wr["results"] == []
        assert wr["error"] is not None
