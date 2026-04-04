"""Tests for graph analytics computation script."""
from __future__ import annotations

from unittest.mock import AsyncMock

import networkx as nx
import pytest

from scripts.compute_graph_analytics import (
    build_networkx_graph,
    compute_communities,
    compute_pagerank,
    compute_rising_authority,
    compute_treatment_aggregation,
    fetch_graph_data,
    invalidate_caches,
    run_analytics,
    write_analytics_to_neo4j,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

sample_nodes = [
    {
        "id": "a",
        "year": 2020,
        "cited_by_count": 10,
        "keywords": "constitutional,article 21",
        "acts_cited": "Constitution of India",
    },
    {
        "id": "b",
        "year": 2018,
        "cited_by_count": 5,
        "keywords": "criminal,murder",
        "acts_cited": "Indian Penal Code",
    },
    {
        "id": "c",
        "year": 2022,
        "cited_by_count": 15,
        "keywords": "constitutional,article 14",
        "acts_cited": "Constitution of India",
    },
    {
        "id": "d",
        "year": 2023,
        "cited_by_count": 2,
        "keywords": "criminal,theft",
        "acts_cited": "Indian Penal Code",
    },
]

sample_edges = [
    {"source": "c", "target": "a", "treatment": "followed"},
    {"source": "d", "target": "b", "treatment": "distinguished"},
    {"source": "c", "target": "b", "treatment": "affirmed"},
    {"source": "d", "target": "a", "treatment": "overruled"},
]


@pytest.fixture()
def sample_graph() -> nx.DiGraph:
    return build_networkx_graph(sample_nodes, sample_edges)


# ---------------------------------------------------------------------------
# TestBuildNetworkxGraph
# ---------------------------------------------------------------------------


class TestBuildNetworkxGraph:
    def test_node_count(self, sample_graph: nx.DiGraph) -> None:
        assert len(sample_graph.nodes) == 4

    def test_edge_count(self, sample_graph: nx.DiGraph) -> None:
        assert len(sample_graph.edges) == 4

    def test_node_attributes_preserved(self, sample_graph: nx.DiGraph) -> None:
        assert sample_graph.nodes["a"]["year"] == 2020
        assert sample_graph.nodes["b"]["keywords"] == "criminal,murder"

    def test_edge_attributes_preserved(self, sample_graph: nx.DiGraph) -> None:
        assert sample_graph.edges["c", "a"]["treatment"] == "followed"
        assert sample_graph.edges["d", "b"]["treatment"] == "distinguished"

    def test_empty_graph(self) -> None:
        G = build_networkx_graph([], [])
        assert len(G.nodes) == 0
        assert len(G.edges) == 0

    def test_nodes_only(self) -> None:
        G = build_networkx_graph(sample_nodes, [])
        assert len(G.nodes) == 4
        assert len(G.edges) == 0


# ---------------------------------------------------------------------------
# TestComputeCommunities
# ---------------------------------------------------------------------------


class TestComputeCommunities:
    def test_all_nodes_assigned(self, sample_graph: nx.DiGraph) -> None:
        result = compute_communities(sample_graph)
        assert set(result.keys()) == {"a", "b", "c", "d"}

    def test_has_community_id(self, sample_graph: nx.DiGraph) -> None:
        result = compute_communities(sample_graph)
        for info in result.values():
            assert "community_id" in info
            assert isinstance(info["community_id"], int)

    def test_has_community_label(self, sample_graph: nx.DiGraph) -> None:
        result = compute_communities(sample_graph)
        for info in result.values():
            assert "community_label" in info
            assert isinstance(info["community_label"], str)
            assert len(info["community_label"]) > 0

    def test_labels_from_keywords(self, sample_graph: nx.DiGraph) -> None:
        result = compute_communities(sample_graph)
        # All labels should contain tokens from the sample data
        all_labels = " ".join(info["community_label"] for info in result.values())
        # At least some known keywords should appear
        known = {"constitutional", "criminal", "article 21", "article 14", "murder", "theft",
                 "Constitution of India", "Indian Penal Code"}
        assert any(kw in all_labels for kw in known)

    def test_empty_graph(self) -> None:
        G = nx.DiGraph()
        result = compute_communities(G)
        assert result == {}


# ---------------------------------------------------------------------------
# TestComputePagerank
# ---------------------------------------------------------------------------


class TestComputePagerank:
    def test_all_nodes_scored(self, sample_graph: nx.DiGraph) -> None:
        result = compute_pagerank(sample_graph)
        assert set(result.keys()) == {"a", "b", "c", "d"}

    def test_scores_in_range(self, sample_graph: nx.DiGraph) -> None:
        result = compute_pagerank(sample_graph)
        for info in result.values():
            assert 0 <= info["pagerank_global"] <= 100

    def test_highly_cited_gets_higher_score(self, sample_graph: nx.DiGraph) -> None:
        result = compute_pagerank(sample_graph)
        # 'a' is cited by both c and d, 'b' is cited by c and d
        # Both have same in-degree, but c and d have no incoming — so a and b should rank higher
        assert result["a"]["pagerank_global"] > result["c"]["pagerank_global"]
        assert result["b"]["pagerank_global"] > result["d"]["pagerank_global"]

    def test_max_score_is_100(self, sample_graph: nx.DiGraph) -> None:
        result = compute_pagerank(sample_graph)
        max_score = max(info["pagerank_global"] for info in result.values())
        assert max_score == 100.0

    def test_per_community_pagerank(self, sample_graph: nx.DiGraph) -> None:
        communities = compute_communities(sample_graph)
        result = compute_pagerank(sample_graph, communities=communities)
        for info in result.values():
            assert "pagerank_community" in info
            assert 0 <= info["pagerank_community"] <= 100

    def test_single_node_community_gets_100(self) -> None:
        G = nx.DiGraph()
        G.add_node("x", keywords="test", acts_cited="")
        communities = {"x": {"community_id": 0, "community_label": "test"}}
        result = compute_pagerank(G, communities=communities)
        assert result["x"]["pagerank_community"] == 100.0

    def test_empty_graph(self) -> None:
        G = nx.DiGraph()
        result = compute_pagerank(G)
        assert result == {}


# ---------------------------------------------------------------------------
# TestComputeRisingAuthority
# ---------------------------------------------------------------------------


class TestComputeRisingAuthority:
    def test_all_nodes_scored(self, sample_graph: nx.DiGraph) -> None:
        result = compute_rising_authority(sample_graph, recent_year_cutoff=2021)
        assert set(result.keys()) == {"a", "b", "c", "d"}

    def test_recent_citations_counted(self, sample_graph: nx.DiGraph) -> None:
        # cutoff 2021: c(2022) and d(2023) are recent, a(2020) and b(2018) are not
        # 'a' is cited by c and d — both recent → ratio = 1.0
        result = compute_rising_authority(sample_graph, recent_year_cutoff=2021)
        assert result["a"]["recent_citation_ratio"] == 1.0

    def test_mixed_citations(self, sample_graph: nx.DiGraph) -> None:
        # cutoff 2022: only d(2023) is recent
        # 'a' is cited by c(2022) and d(2023) → c is at boundary (>=2022 counts) → 2/2
        result = compute_rising_authority(sample_graph, recent_year_cutoff=2022)
        assert result["a"]["recent_citation_ratio"] == 1.0

    def test_no_citations_gets_zero(self, sample_graph: nx.DiGraph) -> None:
        # c and d have no incoming edges
        result = compute_rising_authority(sample_graph, recent_year_cutoff=2021)
        assert result["c"]["recent_citation_ratio"] == 0.0
        assert result["d"]["recent_citation_ratio"] == 0.0

    def test_old_citations_ratio(self, sample_graph: nx.DiGraph) -> None:
        # cutoff 2025: c(2022) and d(2023) are NOT recent
        # 'a' cited by c(2022), d(2023) — neither >= 2025 → 0/2 = 0.0
        result = compute_rising_authority(sample_graph, recent_year_cutoff=2025)
        assert result["a"]["recent_citation_ratio"] == 0.0

    def test_default_cutoff(self, sample_graph: nx.DiGraph) -> None:
        # Should not raise
        result = compute_rising_authority(sample_graph)
        assert len(result) == 4


# ---------------------------------------------------------------------------
# TestComputeTreatmentAggregation
# ---------------------------------------------------------------------------


class TestComputeTreatmentAggregation:
    def test_all_nodes_computed(self, sample_graph: nx.DiGraph) -> None:
        result = compute_treatment_aggregation(sample_graph)
        assert set(result.keys()) == {"a", "b", "c", "d"}

    def test_treatment_counts(self, sample_graph: nx.DiGraph) -> None:
        result = compute_treatment_aggregation(sample_graph)
        # 'a' is cited by c(followed) and d(overruled)
        assert result["a"]["treatment_summary"]["followed"] == 1
        assert result["a"]["treatment_summary"]["overruled"] == 1

    def test_positive_percentage(self, sample_graph: nx.DiGraph) -> None:
        result = compute_treatment_aggregation(sample_graph)
        # 'a': 1 positive (followed) / 2 total = 0.5
        assert result["a"]["treatment_positive_pct"] == 0.5

    def test_all_positive(self, sample_graph: nx.DiGraph) -> None:
        result = compute_treatment_aggregation(sample_graph)
        # 'b': affirmed (positive) + distinguished (neither) → 1/2 = 0.5
        assert result["b"]["treatment_positive_pct"] == 0.5

    def test_no_citations_gets_full_positive(self, sample_graph: nx.DiGraph) -> None:
        result = compute_treatment_aggregation(sample_graph)
        # c and d have no incoming edges → default 1.0
        assert result["c"]["treatment_positive_pct"] == 1.0
        assert result["d"]["treatment_positive_pct"] == 1.0

    def test_empty_summary_for_uncited(self, sample_graph: nx.DiGraph) -> None:
        result = compute_treatment_aggregation(sample_graph)
        assert result["c"]["treatment_summary"] == {}


# ---------------------------------------------------------------------------
# Async tests
# ---------------------------------------------------------------------------


class TestFetchGraphData:
    async def test_fetch_returns_nodes_and_edges(self) -> None:
        mock_store = AsyncMock()
        mock_store.query.side_effect = [
            [{"id": "a", "year": 2020, "cited_by_count": 5, "keywords": "", "acts_cited": ""}],
            [{"source": "b", "target": "a", "treatment": "followed"}],
        ]
        nodes, edges = await fetch_graph_data(mock_store)
        assert len(nodes) == 1
        assert len(edges) == 1
        assert mock_store.query.call_count == 2


class TestWriteAnalytics:
    async def test_writes_batches(self) -> None:
        mock_store = AsyncMock()
        communities = {"a": {"community_id": 0, "community_label": "test"}}
        pagerank = {"a": {"pagerank_global": 100.0, "pagerank_community": 100.0}}
        rising = {"a": {"recent_citation_ratio": 0.5}}
        treatments = {"a": {"treatment_positive_pct": 1.0, "treatment_summary": {}}}

        count = await write_analytics_to_neo4j(
            mock_store,
            communities=communities,
            pagerank=pagerank,
            rising=rising,
            treatments=treatments,
        )
        assert count == 1
        mock_store.query.assert_called_once()

    async def test_handles_many_nodes(self) -> None:
        mock_store = AsyncMock()
        n = 1200
        communities = {str(i): {"community_id": 0, "community_label": "t"} for i in range(n)}
        pagerank = {str(i): {"pagerank_global": 50.0, "pagerank_community": 50.0} for i in range(n)}
        rising = {str(i): {"recent_citation_ratio": 0.0} for i in range(n)}
        treatments = {str(i): {"treatment_positive_pct": 1.0, "treatment_summary": {}} for i in range(n)}

        count = await write_analytics_to_neo4j(
            mock_store,
            communities=communities,
            pagerank=pagerank,
            rising=rising,
            treatments=treatments,
        )
        assert count == n
        # 1200 / 500 = 3 batches
        assert mock_store.query.call_count == 3


class TestInvalidateCaches:
    async def test_deletes_keys(self) -> None:
        mock_redis = AsyncMock()
        await invalidate_caches(mock_redis)
        assert mock_redis.delete.call_count == 3

    async def test_handles_redis_errors(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = ConnectionError("down")
        # Should not raise
        await invalidate_caches(mock_redis)


class TestRunAnalytics:
    async def test_orchestrates_full_pipeline(self) -> None:
        mock_store = AsyncMock()
        mock_store.query.side_effect = [
            # fetch nodes
            sample_nodes,
            # fetch edges
            sample_edges,
            # write batch (all 4 nodes in one batch)
            None,
        ]
        mock_redis = AsyncMock()

        await run_analytics(mock_store, mock_redis)

        # 2 fetches + 1 write batch
        assert mock_store.query.call_count == 3
        # Cache invalidation
        assert mock_redis.delete.call_count == 3

    async def test_skips_empty_graph(self) -> None:
        mock_store = AsyncMock()
        mock_store.query.side_effect = [
            [],  # no nodes
            [],  # no edges
        ]

        await run_analytics(mock_store)
        # Only the 2 fetch queries, no writes
        assert mock_store.query.call_count == 2
