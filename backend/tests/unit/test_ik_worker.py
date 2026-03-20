"""Tests for IK search worker — filter propagation and cost control."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


def _make_task(**overrides) -> dict:
    """Create a minimal IK research task."""
    base = {
        "task_id": "test-ik-1",
        "task_type": "ik_search",
        "nl_query": "Section 498A cruelty",
        "boolean_query": "",
        "named_cases": [],
        "rationale": "test",
        "filters": {},
        "priority": 1,
    }
    base.update(overrides)
    return base


@pytest.fixture
def mock_ik_client():
    client = AsyncMock()
    client.search = AsyncMock(return_value=[
        {"tid": 123, "title": "Test Case", "citation": "(2020) 5 SCC 1", "court": "Supreme Court"}
    ])
    client.get_fragment = AsyncMock(return_value={"headline": ["Relevant passage"]})
    return client


@pytest.fixture(autouse=True)
def _mock_redis():
    """Mock get_redis() so cache calls don't fail in tests."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.setex = AsyncMock(return_value=True)
    with patch("app.core.agents.nodes.worker_nodes.get_redis", new_callable=AsyncMock, return_value=mock_redis):
        yield mock_redis


class TestIKWorkerFilterPropagation:
    """Tests for filter propagation from research plan to IK API."""

    @pytest.mark.asyncio
    async def test_passes_boolean_query(self, mock_ik_client) -> None:
        """boolean_query from task should be passed to IK client."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        state = {"task": _make_task(boolean_query="498A ANDD cruelty ANDD dowry")}
        await ik_search_worker(state, mock_ik_client)

        call_kwargs = mock_ik_client.search.call_args[1]
        assert call_kwargs["boolean_query"] == "498A ANDD cruelty ANDD dowry"

    @pytest.mark.asyncio
    async def test_passes_court_filter(self, mock_ik_client) -> None:
        """court from filters should be passed as court_filter."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        state = {"task": _make_task(filters={"court": "supreme_court"})}
        await ik_search_worker(state, mock_ik_client)

        call_kwargs = mock_ik_client.search.call_args[1]
        assert call_kwargs["court_filter"] == "supreme_court"

    @pytest.mark.asyncio
    async def test_passes_date_range(self, mock_ik_client) -> None:
        """from_year/to_year should be converted to DD-MM-YYYY IK format."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        state = {"task": _make_task(filters={"from_year": 2015, "to_year": 2024})}
        await ik_search_worker(state, mock_ik_client)

        call_kwargs = mock_ik_client.search.call_args[1]
        assert call_kwargs["from_date"] == "01-01-2015"
        assert call_kwargs["to_date"] == "31-12-2024"

    @pytest.mark.asyncio
    async def test_passes_sort_by(self, mock_ik_client) -> None:
        """sort_by from filters should be forwarded."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        state = {"task": _make_task(filters={"sort_by": "mostrecent"})}
        await ik_search_worker(state, mock_ik_client)

        call_kwargs = mock_ik_client.search.call_args[1]
        assert call_kwargs["sort_by"] == "mostrecent"

    @pytest.mark.asyncio
    async def test_no_filters_still_works(self, mock_ik_client) -> None:
        """Empty filters should result in None/default params."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        state = {"task": _make_task()}
        result = await ik_search_worker(state, mock_ik_client)

        assert result["worker_results"][0]["error"] is None
        assert len(result["worker_results"][0]["results"]) == 1

    @pytest.mark.asyncio
    async def test_returns_source_urls(self, mock_ik_client) -> None:
        """Results should include IK source URLs."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        state = {"task": _make_task()}
        result = await ik_search_worker(state, mock_ik_client)

        urls = result["worker_results"][0]["source_urls"]
        assert len(urls) == 1
        assert "indiankanoon.org/doc/123/" in urls[0]


class TestIKWorkerCostControl:
    """Tests for fragment call limiting."""

    @pytest.mark.asyncio
    async def test_limits_fragment_calls(self) -> None:
        """Fragment API calls should be limited to _MAX_IK_FRAGMENT_CALLS."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker, _MAX_IK_FRAGMENT_CALLS

        mock_ik = AsyncMock()
        mock_ik.search = AsyncMock(return_value=[
            {"tid": i, "title": f"Case {i}", "citation": f"(2020) {i} SCC 1"}
            for i in range(10)
        ])
        mock_ik.get_fragment = AsyncMock(return_value={"headline": ["test passage"]})

        state = {"task": _make_task()}
        await ik_search_worker(state, mock_ik)

        assert mock_ik.get_fragment.call_count == _MAX_IK_FRAGMENT_CALLS

    @pytest.mark.asyncio
    async def test_results_without_fragments_still_included(self) -> None:
        """Results beyond the fragment limit should still be included (without snippet)."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        mock_ik = AsyncMock()
        mock_ik.search = AsyncMock(return_value=[
            {"tid": i, "title": f"Case {i}"} for i in range(8)
        ])
        mock_ik.get_fragment = AsyncMock(return_value={"headline": ["frag"]})

        state = {"task": _make_task()}
        result = await ik_search_worker(state, mock_ik)

        all_results = result["worker_results"][0]["results"]
        assert len(all_results) == 8  # All included
        # Last 3 should have empty snippet (beyond fragment limit)
        assert all_results[7]["snippet"] == ""
