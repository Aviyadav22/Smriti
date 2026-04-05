"""Unit tests for citation graph traversal functions."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.graph.traversal import (
    MAX_NODES,
    _TREATMENT_TO_DISPLAY,
    get_authorities,
    get_citation_chain,
    get_dashboard,
    get_graph_stats,
    get_neighborhood,
    get_shortest_path,
    get_treatment_summary,
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

        # Verify the query was called with depth capped at 3 (embedded in Cypher f-string)
        call_args = store.query.call_args
        assert "*1..3" in call_args.kwargs["cypher"]

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
        assert "*1..5" in call_args.kwargs["cypher"]

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


# ---------------------------------------------------------------------------
# Treatment normalization
# ---------------------------------------------------------------------------


class TestTreatmentNormalization:
    """Test that edge treatment properties are normalized to display types."""

    @pytest.mark.asyncio
    async def test_overruled_treatment_becomes_overrules(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "case_2",
                    "title": "Overruled Case",
                    "citation": None,
                    "court": "SC",
                    "year": 2020,
                    "cited_by_count": 1,
                    "edges": [
                        {"from": "case_1", "to": "case_2", "type": "CITES", "treatment": "overruled", "context": None},
                    ],
                },
            ],
            get_node_return={"id": "case_1", "title": "Center"},
        )
        result = await get_neighborhood("case_1", graph_store=store, depth=1)
        assert result["edges"][0]["type"] == "overrules"

    @pytest.mark.asyncio
    async def test_affirmed_treatment_becomes_affirms(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "case_2",
                    "title": "Affirmed Case",
                    "citation": None,
                    "court": "SC",
                    "year": 2020,
                    "cited_by_count": 1,
                    "edges": [
                        {"from": "case_1", "to": "case_2", "type": "CITES", "treatment": "affirmed", "context": None},
                    ],
                },
            ],
            get_node_return={"id": "case_1", "title": "Center"},
        )
        result = await get_neighborhood("case_1", graph_store=store, depth=1)
        assert result["edges"][0]["type"] == "affirms"

    @pytest.mark.asyncio
    async def test_distinguished_treatment_becomes_distinguishes(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "case_2",
                    "title": "Distinguished Case",
                    "citation": None,
                    "court": "SC",
                    "year": 2020,
                    "cited_by_count": 1,
                    "edges": [
                        {"from": "case_1", "to": "case_2", "type": "CITES", "treatment": "distinguished", "context": None},
                    ],
                },
            ],
            get_node_return={"id": "case_1", "title": "Center"},
        )
        result = await get_neighborhood("case_1", graph_store=store, depth=1)
        assert result["edges"][0]["type"] == "distinguishes"

    @pytest.mark.asyncio
    async def test_null_treatment_becomes_cites(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "case_2",
                    "title": "Cited Case",
                    "citation": None,
                    "court": "SC",
                    "year": 2020,
                    "cited_by_count": 1,
                    "edges": [
                        {"from": "case_1", "to": "case_2", "type": "CITES", "treatment": None, "context": None},
                    ],
                },
            ],
            get_node_return={"id": "case_1", "title": "Center"},
        )
        result = await get_neighborhood("case_1", graph_store=store, depth=1)
        assert result["edges"][0]["type"] == "cites"

    @pytest.mark.asyncio
    async def test_referred_to_treatment_becomes_cites(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "case_2",
                    "title": "Referred Case",
                    "citation": None,
                    "court": "SC",
                    "year": 2020,
                    "cited_by_count": 1,
                    "edges": [
                        {"from": "case_1", "to": "case_2", "type": "CITES", "treatment": "referred_to", "context": None},
                    ],
                },
            ],
            get_node_return={"id": "case_1", "title": "Center"},
        )
        result = await get_neighborhood("case_1", graph_store=store, depth=1)
        assert result["edges"][0]["type"] == "cites"

    def test_all_treatment_types_mapped(self) -> None:
        """Every treatment value in the mapping produces the expected display type."""
        expected = {
            "overruled": "overrules",
            "affirmed": "affirms",
            "distinguished": "distinguishes",
            "followed": "followed",
            "not_followed": "not_followed",
            "doubted": "doubted",
            "explained": "explained",
            "per_incuriam": "per_incuriam",
            "referred_to": "cites",
            None: "cites",
        }
        for treatment, display in expected.items():
            assert _TREATMENT_TO_DISPLAY[treatment] == display, (
                f"Treatment {treatment!r} should map to {display!r}"
            )

    @pytest.mark.asyncio
    async def test_citation_chain_also_normalizes_treatment(self) -> None:
        store = _make_graph_store(
            query_return=[
                {
                    "id": "cited_1",
                    "title": "Overruled in Chain",
                    "citation": None,
                    "court": "SC",
                    "year": 2018,
                    "cited_by_count": 3,
                    "edges": [
                        {"from": "case_1", "to": "cited_1", "type": "CITES", "treatment": "overruled"},
                    ],
                },
            ],
        )
        result = await get_citation_chain("case_1", graph_store=store, max_depth=2)
        assert len(result["edges"]) == 1
        assert result["edges"][0]["type"] == "overrules"


# ---------------------------------------------------------------------------
# get_dashboard
# ---------------------------------------------------------------------------


class TestGetDashboard:
    """Test dashboard data queries."""

    @pytest.mark.asyncio
    async def test_returns_all_sections(self) -> None:
        store = AsyncMock()
        store.query = AsyncMock(
            side_effect=[
                # most_cited
                [{"id": "mc1", "title": "Most Cited", "citation": "X", "court": "SC", "year": 2020, "cited_by_count": 100, "pagerank_global": 0.9, "community_id": 1, "community_label": "Constitutional", "recent_citation_ratio": 0.3}],
                # rising
                [{"id": "r1", "title": "Rising Case", "citation": "Y", "court": "SC", "year": 2023, "cited_by_count": 10, "pagerank_global": 0.5, "community_id": 2, "community_label": "Criminal", "recent_citation_ratio": 0.6}],
                # recently_negative
                [{"id": "neg1", "title": "Neg Case", "citation": "Z", "court": "SC", "year": 2019, "cited_by_count": 50, "pagerank_global": 0.7, "community_id": 1, "community_label": "Constitutional", "recent_citation_ratio": 0.1, "negative_treatment": "overruled", "by_case_title": "New Case", "by_case_year": 2024}],
                # communities
                [{"community_id": 1, "community_label": "Constitutional", "count": 200}, {"community_id": 2, "community_label": "Criminal", "count": 150}],
                # get_subtopics query
                [],
                # get_statute_sections query
                [],
            ]
        )
        result = await get_dashboard(graph_store=store, redis_client=None)

        assert "most_cited" in result
        assert "rising" in result
        assert "recently_negative" in result
        assert "communities" in result
        assert "subtopics" in result
        assert "statute_sections" in result
        assert len(result["most_cited"]) == 1
        assert len(result["rising"]) == 1
        assert len(result["recently_negative"]) == 1
        assert len(result["communities"]) == 2

    @pytest.mark.asyncio
    async def test_community_filter_passes_param(self) -> None:
        store = AsyncMock()
        store.query = AsyncMock(return_value=[])
        await get_dashboard(graph_store=store, redis_client=None, community_label="Criminal Law")

        # 4 dashboard queries + 1 subtopics + 1 statute_sections = 6
        assert store.query.call_count == 6
        # Check that at least the first query includes community_label filter
        first_call = store.query.call_args_list[0]
        assert "community_label" in first_call.kwargs["cypher"]

    @pytest.mark.asyncio
    async def test_caches_result(self) -> None:
        import json

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()

        store = AsyncMock()
        store.query = AsyncMock(return_value=[])

        await get_dashboard(graph_store=store, redis_client=redis)

        # get_dashboard caches dashboard + get_subtopics + get_statute_sections = 3 calls
        assert redis.setex.call_count >= 1
        # Verify the dashboard cache key is among the calls
        cache_keys = [call.args[0] for call in redis.setex.call_args_list]
        assert any(k.startswith("graph:dashboard:") for k in cache_keys)
        # Verify TTL is 1 hour for the dashboard entry
        for call in redis.setex.call_args_list:
            if call.args[0].startswith("graph:dashboard:"):
                assert call.args[1] == 3600  # 1 hour TTL

    @pytest.mark.asyncio
    async def test_returns_from_cache(self) -> None:
        import json

        cached = {"most_cited": [], "rising": [], "recently_negative": [], "communities": []}
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=json.dumps(cached))

        store = AsyncMock()
        store.query = AsyncMock()

        result = await get_dashboard(graph_store=store, redis_client=redis)

        assert result == cached
        store.query.assert_not_called()


# ---------------------------------------------------------------------------
# get_shortest_path
# ---------------------------------------------------------------------------


class TestGetShortestPath:
    """Test shortest path queries."""

    @pytest.mark.asyncio
    async def test_finds_path(self) -> None:
        store = AsyncMock()
        from_node = {"id": "a", "title": "Case A", "citation": "X", "court": "SC", "year": 2020, "cited_by_count": 10}
        to_node = {"id": "b", "title": "Case B", "citation": "Y", "court": "SC", "year": 2021, "cited_by_count": 5}
        store.get_node = AsyncMock(side_effect=[from_node, to_node])
        store.query = AsyncMock(
            side_effect=[
                # forward path
                [{"node_ids": ["a", "b"], "edges": [{"from": "a", "to": "b", "treatment": None, "context": None}]}],
                # reverse path (empty)
                [],
            ]
        )

        result = await get_shortest_path("a", "b", graph_store=store)

        assert "paths" in result
        assert len(result["paths"]) == 1
        assert result["from_case"]["id"] == "a"
        assert result["to_case"]["id"] == "b"

    @pytest.mark.asyncio
    async def test_no_path_returns_empty(self) -> None:
        store = AsyncMock()
        store.get_node = AsyncMock(side_effect=[
            {"id": "a", "title": "A"},
            {"id": "b", "title": "B"},
        ])
        store.query = AsyncMock(return_value=[])

        result = await get_shortest_path("a", "b", graph_store=store)

        assert result["paths"] == []

    @pytest.mark.asyncio
    async def test_missing_node_returns_error(self) -> None:
        store = AsyncMock()
        store.get_node = AsyncMock(side_effect=[None, {"id": "b", "title": "B"}])

        result = await get_shortest_path("a", "b", graph_store=store)

        assert "error" in result
        assert result["paths"] == []


# ---------------------------------------------------------------------------
# get_treatment_summary
# ---------------------------------------------------------------------------


class TestGetTreatmentSummary:
    """Test treatment summary queries."""

    @pytest.mark.asyncio
    async def test_returns_breakdown(self) -> None:
        store = AsyncMock()
        store.get_node = AsyncMock(return_value={"id": "case_1", "title": "Target"})
        store.query = AsyncMock(return_value=[
            {"id": "c1", "title": "Citing 1", "year": 2022, "citation": "X", "context": None, "treatment": "followed"},
            {"id": "c2", "title": "Citing 2", "year": 2023, "citation": "Y", "context": None, "treatment": "followed"},
            {"id": "c3", "title": "Citing 3", "year": 2024, "citation": "Z", "context": None, "treatment": "distinguished"},
        ])

        result = await get_treatment_summary("case_1", graph_store=store, redis_client=None)

        assert result["case_id"] == "case_1"
        assert result["total_citations"] == 3
        assert "followed" in result["breakdown"]
        assert len(result["breakdown"]["followed"]) == 2
        assert "distinguished" in result["breakdown"]
        assert len(result["breakdown"]["distinguished"]) == 1

    @pytest.mark.asyncio
    async def test_verdict_overruled(self) -> None:
        store = AsyncMock()
        store.get_node = AsyncMock(return_value={"id": "case_1"})
        store.query = AsyncMock(return_value=[
            {"id": "c1", "title": "A", "year": 2022, "citation": None, "context": None, "treatment": "overruled"},
            {"id": "c2", "title": "B", "year": 2023, "citation": None, "context": None, "treatment": "followed"},
        ])

        result = await get_treatment_summary("case_1", graph_store=store, redis_client=None)
        assert result["verdict"] == "Overruled"

    @pytest.mark.asyncio
    async def test_verdict_followed(self) -> None:
        store = AsyncMock()
        store.get_node = AsyncMock(return_value={"id": "case_1"})
        # All positive: 4 followed + 1 affirmed = 5/5 = 100% positive -> "Followed"
        store.query = AsyncMock(return_value=[
            {"id": "c1", "title": "A", "year": 2022, "citation": None, "context": None, "treatment": "followed"},
            {"id": "c2", "title": "B", "year": 2023, "citation": None, "context": None, "treatment": "followed"},
            {"id": "c3", "title": "C", "year": 2023, "citation": None, "context": None, "treatment": "followed"},
            {"id": "c4", "title": "D", "year": 2024, "citation": None, "context": None, "treatment": "affirmed"},
            {"id": "c5", "title": "E", "year": 2024, "citation": None, "context": None, "treatment": "followed"},
        ])

        result = await get_treatment_summary("case_1", graph_store=store, redis_client=None)
        assert result["verdict"] == "Followed"

    @pytest.mark.asyncio
    async def test_verdict_cautionary(self) -> None:
        store = AsyncMock()
        store.get_node = AsyncMock(return_value={"id": "case_1"})
        # 1 followed + 2 distinguished + 1 doubted = 1/4 positive (25%) -> "Cautionary"
        # (no severe negatives like overruled/per_incuriam)
        store.query = AsyncMock(return_value=[
            {"id": "c1", "title": "A", "year": 2022, "citation": None, "context": None, "treatment": "followed"},
            {"id": "c2", "title": "B", "year": 2023, "citation": None, "context": None, "treatment": "distinguished"},
            {"id": "c3", "title": "C", "year": 2023, "citation": None, "context": None, "treatment": "distinguished"},
            {"id": "c4", "title": "D", "year": 2024, "citation": None, "context": None, "treatment": "doubted"},
        ])

        result = await get_treatment_summary("case_1", graph_store=store, redis_client=None)
        assert result["verdict"] == "Cautionary"

    @pytest.mark.asyncio
    async def test_missing_case(self) -> None:
        store = AsyncMock()
        store.get_node = AsyncMock(return_value=None)

        result = await get_treatment_summary("nonexistent", graph_store=store, redis_client=None)
        assert "error" in result
