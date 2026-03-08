"""Unit tests for citation graph traversal functions."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.graph.traversal import (
    MAX_NODES,
    get_authorities,
    get_citation_chain,
    get_graph_stats,
    get_neighborhood,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_graph_store(
    query_return: list[dict] | None = None,
    get_node_return: dict | None = None,
    raise_on_query: Exception | None = None,
) -> AsyncMock:
    """Create a mock GraphStore with configurable return values."""
    store = AsyncMock()

    if raise_on_query:
        store.query = AsyncMock(side_effect=raise_on_query)
        store.get_node = AsyncMock(side_effect=raise_on_query)
    else:
        store.query = AsyncMock(return_value=query_return or [])
        store.get_node = AsyncMock(return_value=get_node_return)

    return store


# ---------------------------------------------------------------------------
# get_neighborhood
# ---------------------------------------------------------------------------


class TestGetNeighborhood:
    """Test citation neighborhood queries."""

    @pytest.mark.asyncio
    async def test_empty_graph(self) -> None:
        store = _make_graph_store(query_return=[], get_node_return={"id": "case_1"})
        result = await get_neighborhood("case_1", graph_store=store, depth=1)

        assert "nodes" in result
        assert "edges" in result
        assert len(result["nodes"]) == 1  # center node only
        assert len(result["edges"]) == 0

    @pytest.mark.asyncio
    async def test_with_neighbors(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "case_2",
                    "title": "Neighbor Case",
                    "citation": "(2020) 1 SCC 2",
                    "court": "Supreme Court of India",
                    "year": 2020,
                    "cited_by_count": 5,
                    "edges": [
                        {"from": "case_1", "to": "case_2", "type": "CITES", "context": None},
                    ],
                },
            ],
            get_node_return={
                "id": "case_1",
                "title": "Center Case",
                "citation": "(2019) 1 SCC 1",
                "court": "Supreme Court of India",
                "year": 2019,
                "cited_by_count": 10,
            },
        )

        result = await get_neighborhood("case_1", graph_store=store, depth=1)

        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1
        assert result["edges"][0]["from"] == "case_1"
        assert result["edges"][0]["to"] == "case_2"

    @pytest.mark.asyncio
    async def test_depth_capped_at_3(self) -> None:
        store = _make_graph_store(get_node_return={"id": "case_1"})
        await get_neighborhood("case_1", graph_store=store, depth=10)

        # Verify the query was called with depth capped at 3
        call_args = store.query.call_args
        assert call_args.kwargs["params"]["depth"] == 3

    @pytest.mark.asyncio
    async def test_deduplicates_edges(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "case_2",
                    "edges": [
                        {"from": "case_1", "to": "case_2", "type": "CITES"},
                    ],
                },
                {
                    "id": "case_3",
                    "edges": [
                        {"from": "case_1", "to": "case_2", "type": "CITES"},  # duplicate
                        {"from": "case_1", "to": "case_3", "type": "CITES"},
                    ],
                },
            ],
            get_node_return={"id": "case_1"},
        )

        result = await get_neighborhood("case_1", graph_store=store, depth=2)
        assert len(result["edges"]) == 2  # deduped, not 3

    @pytest.mark.asyncio
    async def test_handles_connection_error(self) -> None:
        store = _make_graph_store(raise_on_query=ConnectionError("Neo4j down"))
        result = await get_neighborhood("case_1", graph_store=store, depth=1)

        assert result == {"nodes": [], "edges": []}


# ---------------------------------------------------------------------------
# get_citation_chain
# ---------------------------------------------------------------------------


class TestGetCitationChain:
    """Test forward citation chain queries."""

    @pytest.mark.asyncio
    async def test_empty_chain(self) -> None:
        store = _make_graph_store(query_return=[])
        result = await get_citation_chain("case_1", graph_store=store, max_depth=3)

        assert len(result["nodes"]) == 1  # start node only
        assert result["nodes"][0]["id"] == "case_1"
        assert len(result["edges"]) == 0

    @pytest.mark.asyncio
    async def test_with_citations(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "cited_1",
                    "title": "Cited Case",
                    "citation": None,
                    "court": "SC",
                    "year": 2018,
                    "cited_by_count": 3,
                    "edges": [
                        {"from": "case_1", "to": "cited_1"},
                    ],
                },
            ]
        )
        result = await get_citation_chain("case_1", graph_store=store, max_depth=2)

        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1

    @pytest.mark.asyncio
    async def test_max_depth_capped_at_5(self) -> None:
        store = _make_graph_store()
        await get_citation_chain("case_1", graph_store=store, max_depth=20)

        call_args = store.query.call_args
        assert call_args.kwargs["params"]["depth"] == 5

    @pytest.mark.asyncio
    async def test_handles_runtime_error(self) -> None:
        store = _make_graph_store(raise_on_query=RuntimeError("Query timeout"))
        result = await get_citation_chain("case_1", graph_store=store, max_depth=3)

        assert result == {"nodes": [], "edges": []}


# ---------------------------------------------------------------------------
# get_authorities
# ---------------------------------------------------------------------------


class TestGetAuthorities:
    """Test authority ranking queries."""

    @pytest.mark.asyncio
    async def test_returns_authorities(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "auth_1",
                    "title": "Landmark Case",
                    "citation": "(2017) 10 SCC 1",
                    "court": "SC",
                    "year": 2017,
                    "cited_by_count": 100,
                },
                {
                    "id": "auth_2",
                    "title": "Another Case",
                    "citation": None,
                    "court": "SC",
                    "year": 2015,
                    "cited_by_count": 50,
                },
            ]
        )
        result = await get_authorities("case_1", graph_store=store, limit=10)

        assert len(result) == 2
        assert result[0]["id"] == "auth_1"
        assert result[0]["cited_by_count"] == 100
        assert result[1]["cited_by_count"] == 50

    @pytest.mark.asyncio
    async def test_empty_result(self) -> None:
        store = _make_graph_store(query_return=[])
        result = await get_authorities("case_1", graph_store=store)
        assert result == []

    @pytest.mark.asyncio
    async def test_handles_connection_error(self) -> None:
        store = _make_graph_store(raise_on_query=ConnectionError("Unavailable"))
        result = await get_authorities("case_1", graph_store=store)
        assert result == []


# ---------------------------------------------------------------------------
# get_graph_stats
# ---------------------------------------------------------------------------


class TestGetGraphStats:
    """Test global graph statistics."""

    @pytest.mark.asyncio
    async def test_returns_stats(self) -> None:
        store = AsyncMock()
        store.query = AsyncMock(
            side_effect=[
                [{"total_judgments": 796}],
                [{"total_edges": 5000}],
                [
                    {"id": "top1", "title": "Top Case", "citation": "X", "cited_by_count": 200},
                ],
            ]
        )
        result = await get_graph_stats(graph_store=store, redis_client=None)

        assert result["total_judgments"] == 796
        assert result["total_edges"] == 5000
        assert len(result["most_cited"]) == 1
        assert result["most_cited"][0]["cited_by_count"] == 200

    @pytest.mark.asyncio
    async def test_connection_error_returns_zeros(self) -> None:
        store = _make_graph_store(raise_on_query=ConnectionError("Neo4j down"))
        result = await get_graph_stats(graph_store=store, redis_client=None)

        assert result == {"total_judgments": 0, "total_edges": 0, "most_cited": []}

    @pytest.mark.asyncio
    async def test_uses_redis_cache(self) -> None:
        import json

        cached_stats = {"total_judgments": 100, "total_edges": 500, "most_cited": []}
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=json.dumps(cached_stats))

        store = _make_graph_store()
        result = await get_graph_stats(graph_store=store, redis_client=redis)

        assert result == cached_stats
        store.query.assert_not_called()  # should use cache, not query

    @pytest.mark.asyncio
    async def test_caches_result_in_redis(self) -> None:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()

        store = AsyncMock()
        store.query = AsyncMock(
            side_effect=[
                [{"total_judgments": 10}],
                [{"total_edges": 20}],
                [],
            ]
        )

        await get_graph_stats(graph_store=store, redis_client=redis)

        redis.setex.assert_called_once()
        call_args = redis.setex.call_args
        assert call_args.args[1] == 900  # 15 min TTL
