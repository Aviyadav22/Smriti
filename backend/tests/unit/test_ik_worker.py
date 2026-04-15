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
    client.search = AsyncMock(
        return_value=[
            {
                "tid": 123,
                "title": "Test Case",
                "citation": "(2020) 5 SCC 1",
                "court": "Supreme Court",
            }
        ]
    )
    client.get_fragment = AsyncMock(return_value={"headline": ["Relevant passage"]})
    return client


@pytest.fixture(autouse=True)
def _mock_redis():
    """Mock get_redis() so cache calls don't fail in tests."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.setex = AsyncMock(return_value=True)
    with patch(
        "app.core.agents.nodes.worker_nodes.get_redis",
        new_callable=AsyncMock,
        return_value=mock_redis,
    ):
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
    async def test_passes_title_filter(self, mock_ik_client) -> None:
        """title from filters should be passed as title_filter."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        state = {"task": _make_task(filters={"title": "Puttaswamy"})}
        await ik_search_worker(state, mock_ik_client)
        call_kwargs = mock_ik_client.search.call_args[1]
        assert call_kwargs["title_filter"] == "Puttaswamy"

    @pytest.mark.asyncio
    async def test_passes_author_filter(self, mock_ik_client) -> None:
        """author from filters should be passed as author_filter."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        state = {"task": _make_task(filters={"author": "chandrachud"})}
        await ik_search_worker(state, mock_ik_client)
        call_kwargs = mock_ik_client.search.call_args[1]
        assert call_kwargs["author_filter"] == "chandrachud"

    @pytest.mark.asyncio
    async def test_passes_bench_filter(self, mock_ik_client) -> None:
        """bench from filters should be passed as bench_filter."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        state = {"task": _make_task(filters={"bench": "nariman"})}
        await ik_search_worker(state, mock_ik_client)
        call_kwargs = mock_ik_client.search.call_args[1]
        assert call_kwargs["bench_filter"] == "nariman"

    @pytest.mark.asyncio
    async def test_passes_maxcites(self, mock_ik_client) -> None:
        """Worker should always request max_cites=5 for free citation data."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        state = {"task": _make_task()}
        await ik_search_worker(state, mock_ik_client)
        call_kwargs = mock_ik_client.search.call_args[1]
        assert call_kwargs["max_cites"] == 5

    @pytest.mark.asyncio
    async def test_extracts_rich_fields(self, mock_ik_client) -> None:
        """Worker should extract docsource, author, publishdate, numcites from search results."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        mock_ik_client.search = AsyncMock(
            return_value=[
                {
                    "tid": 123,
                    "title": "Test Case",
                    "citation": "(2020) 5 SCC 1",
                    "docsource": "Supreme Court of India",
                    "author": "D Y Chandrachud",
                    "publishdate": "2020-03-15",
                    "numcites": 12,
                    "numcitedby": 45,
                    "headline": "A" * 60,  # long enough to skip fragment call
                }
            ]
        )
        state = {"task": _make_task()}
        result = await ik_search_worker(state, mock_ik_client)

        r = result["worker_results"][0]["results"][0]
        assert r["court"] == "Supreme Court of India"
        assert r["author"] == "D Y Chandrachud"
        assert r["date"] == "2020-03-15"
        assert r["num_cited_by"] == 45
        assert r["num_cites"] == 12

    @pytest.mark.asyncio
    async def test_no_filters_still_works(self, mock_ik_client) -> None:
        """Empty filters should result in None/default params."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        state = {"task": _make_task()}
        result = await ik_search_worker(state, mock_ik_client)

        assert result["worker_results"][0]["error"] is None
        assert len(result["worker_results"][0]["results"]) == 1

    @pytest.mark.asyncio
    async def test_includes_court_copy_url(self, mock_ik_client) -> None:
        """Results should include court_copy_url for trusted references."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        state = {"task": _make_task()}
        result = await ik_search_worker(state, mock_ik_client)

        r = result["worker_results"][0]["results"][0]
        assert r["court_copy_url"] == "https://indiankanoon.org/origdoc/123/"

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
        from app.core.agents.nodes.worker_nodes import _MAX_IK_FRAGMENT_CALLS, ik_search_worker

        mock_ik = AsyncMock()
        mock_ik.search = AsyncMock(
            return_value=[
                {"tid": i, "title": f"Case {i}", "citation": f"(2020) {i} SCC 1"} for i in range(10)
            ]
        )
        mock_ik.get_fragment = AsyncMock(return_value={"headline": ["test passage"]})

        state = {"task": _make_task()}
        await ik_search_worker(state, mock_ik)

        assert mock_ik.get_fragment.call_count == _MAX_IK_FRAGMENT_CALLS

    @pytest.mark.asyncio
    async def test_results_without_fragments_still_included(self) -> None:
        """Results beyond the fragment limit should still be included (without snippet)."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        mock_ik = AsyncMock()
        mock_ik.search = AsyncMock(
            return_value=[{"tid": i, "title": f"Case {i}"} for i in range(8)]
        )
        mock_ik.get_fragment = AsyncMock(return_value={"headline": ["frag"]})

        state = {"task": _make_task()}
        result = await ik_search_worker(state, mock_ik)

        all_results = result["worker_results"][0]["results"]
        assert len(all_results) == 8  # All included
        # Last 3 should have empty snippet (beyond fragment limit)
        assert all_results[7]["snippet"] == ""

    @pytest.mark.asyncio
    async def test_uses_search_headline_skips_fragment(self) -> None:
        """Results beyond top-3 with long headline skip fragment API call."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        # Top 3 always get fragment; result at index 3+ uses headline if long enough
        mock_ik = AsyncMock()
        mock_ik.search = AsyncMock(
            return_value=[
                {"tid": 1, "title": "Case 1", "headline": "A" * 60},
                {"tid": 2, "title": "Case 2", "headline": "B" * 60},
                {"tid": 3, "title": "Case 3", "headline": "C" * 60},
                {"tid": 4, "title": "Case 4", "headline": "D" * 60},  # idx 3: headline used
            ]
        )
        mock_ik.get_fragment = AsyncMock(return_value={"headline": ["frag"]})

        state = {"task": _make_task()}
        result = await ik_search_worker(state, mock_ik)

        # Top 3 get fragment calls, 4th uses headline
        assert mock_ik.get_fragment.call_count == 3
        assert result["worker_results"][0]["results"][3]["snippet"] == "D" * 60

    @pytest.mark.asyncio
    async def test_falls_back_to_fragment_when_headline_short(self) -> None:
        """When search headline is too short, call fragment API."""
        from app.core.agents.nodes.worker_nodes import ik_search_worker

        mock_ik = AsyncMock()
        mock_ik.search = AsyncMock(
            return_value=[
                {"tid": 1, "title": "Case 1", "headline": "short"},
            ]
        )
        mock_ik.get_fragment = AsyncMock(
            return_value={"headline": ["Detailed fragment passage about the case"]}
        )

        state = {"task": _make_task()}
        result = await ik_search_worker(state, mock_ik)

        assert mock_ik.get_fragment.call_count == 1
        assert "Detailed fragment passage" in result["worker_results"][0]["results"][0]["snippet"]
