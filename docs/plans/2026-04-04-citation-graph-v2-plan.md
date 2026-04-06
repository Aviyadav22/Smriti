# Citation Graph Explorer v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the graph page from an empty search box into a case validation and discovery tool with dashboard, timeline view, enhanced network view, and precomputed analytics.

**Architecture:** Precompute graph analytics (Louvain communities, topic-sensitive PageRank, treatment aggregation) via a CLI script, store as Neo4j node properties, expose via new API endpoints, render in a redesigned frontend with three modes (Dashboard, Timeline, Network).

**Tech Stack:** Neo4j GDS (self-hosted), Python networkx (fallback), FastAPI endpoints, React + D3/react-force-graph-2d, Redis caching, vitest for tests.

**Design doc:** `docs/plans/2026-04-04-citation-graph-v2-design.md`

---

## Task 1: Extend GraphNode Types and API Models

**Files:**
- Modify: `frontend/src/lib/types.ts:202-232`
- Modify: `backend/app/core/graph/traversal.py:72-110` (node building)

**Step 1: Add new fields to frontend GraphNode type**

In `frontend/src/lib/types.ts`, update the `GraphNode` interface:

```typescript
export interface GraphNode {
    id: string;
    title: string | null;
    citation: string | null;
    court: string | null;
    year: number | null;
    cited_by_count: number;
    // v2 analytics fields
    pagerank_global: number | null;
    pagerank_community: number | null;
    community_id: number | null;
    community_label: string | null;
    recent_citation_ratio: number | null;
    treatment_positive_pct: number | null;
    treatment_summary: Record<string, number> | null;
    bench_type: string | null;
    case_type: string | null;
    ratio: string | null;
}
```

**Step 2: Add DashboardData and PathData types**

In `frontend/src/lib/types.ts`, add after GraphStats:

```typescript
export interface DashboardData {
    most_cited: GraphNode[];
    rising: GraphNode[];
    recently_negative: {
        case: GraphNode;
        negative_treatment: string;
        by_case_title: string | null;
        by_case_year: number | null;
    }[];
    communities: { id: number; label: string; case_count: number }[];
}

export interface PathResult {
    paths: { nodes: GraphNode[]; edges: GraphEdge[] }[];
    from_case: GraphNode;
    to_case: GraphNode;
}
```

**Step 3: Verify types compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (no type errors)

**Step 4: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat(graph-v2): extend GraphNode types with analytics fields"
```

---

## Task 2: Analytics Computation Script

**Files:**
- Create: `backend/scripts/compute_graph_analytics.py`
- Test: `backend/tests/unit/test_graph_analytics.py`

**Step 1: Write tests for analytics functions**

Create `backend/tests/unit/test_graph_analytics.py`:

```python
"""Tests for graph analytics computation."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from scripts.compute_graph_analytics import (
    compute_communities,
    compute_pagerank,
    compute_rising_authority,
    compute_treatment_aggregation,
    build_networkx_graph,
)


@pytest.fixture
def mock_graph_store():
    store = AsyncMock()
    return store


@pytest.fixture
def sample_nodes():
    return [
        {"id": "a", "year": 2020, "cited_by_count": 10, "keywords": "constitutional,article 21", "acts_cited": "Constitution of India"},
        {"id": "b", "year": 2018, "cited_by_count": 5, "keywords": "criminal,murder", "acts_cited": "Indian Penal Code"},
        {"id": "c", "year": 2022, "cited_by_count": 15, "keywords": "constitutional,article 14", "acts_cited": "Constitution of India"},
        {"id": "d", "year": 2023, "cited_by_count": 2, "keywords": "criminal,theft", "acts_cited": "Indian Penal Code"},
    ]


@pytest.fixture
def sample_edges():
    return [
        {"source": "c", "target": "a", "treatment": "followed"},
        {"source": "d", "target": "b", "treatment": "distinguished"},
        {"source": "c", "target": "b", "treatment": "affirmed"},
        {"source": "d", "target": "a", "treatment": "overruled"},
    ]


class TestBuildNetworkxGraph:
    def test_builds_directed_graph(self, sample_nodes, sample_edges):
        G = build_networkx_graph(sample_nodes, sample_edges)
        assert G.number_of_nodes() == 4
        assert G.number_of_edges() == 4
        assert G.is_directed()

    def test_node_attributes_preserved(self, sample_nodes, sample_edges):
        G = build_networkx_graph(sample_nodes, sample_edges)
        assert G.nodes["a"]["year"] == 2020
        assert G.nodes["a"]["cited_by_count"] == 10

    def test_edge_treatment_preserved(self, sample_nodes, sample_edges):
        G = build_networkx_graph(sample_nodes, sample_edges)
        assert G.edges["c", "a"]["treatment"] == "followed"


class TestComputeCommunities:
    def test_assigns_community_ids(self, sample_nodes, sample_edges):
        G = build_networkx_graph(sample_nodes, sample_edges)
        communities = compute_communities(G)
        # Every node gets a community_id
        assert set(communities.keys()) == {"a", "b", "c", "d"}
        for node_id, info in communities.items():
            assert "community_id" in info
            assert "community_label" in info
            assert isinstance(info["community_id"], int)
            assert isinstance(info["community_label"], str)

    def test_labels_from_keywords(self, sample_nodes, sample_edges):
        G = build_networkx_graph(sample_nodes, sample_edges)
        communities = compute_communities(G)
        # Labels should be derived from most common keywords/acts
        labels = {info["community_label"] for info in communities.values()}
        assert len(labels) >= 1  # At least one unique label


class TestComputePagerank:
    def test_global_pagerank(self, sample_nodes, sample_edges):
        G = build_networkx_graph(sample_nodes, sample_edges)
        scores = compute_pagerank(G)
        assert set(scores.keys()) == {"a", "b", "c", "d"}
        for node_id, info in scores.items():
            assert 0 <= info["pagerank_global"] <= 100
            assert 0 <= info["pagerank_community"] <= 100

    def test_highly_cited_gets_higher_score(self, sample_nodes, sample_edges):
        G = build_networkx_graph(sample_nodes, sample_edges)
        communities = compute_communities(G)
        scores = compute_pagerank(G, communities=communities)
        # 'a' is cited by both c and d, should have high score
        assert scores["a"]["pagerank_global"] > scores["d"]["pagerank_global"]


class TestComputeRisingAuthority:
    def test_recent_citation_ratio(self, sample_nodes, sample_edges):
        G = build_networkx_graph(sample_nodes, sample_edges)
        ratios = compute_rising_authority(G, recent_year_cutoff=2021)
        assert set(ratios.keys()) == {"a", "b", "c", "d"}
        for node_id, info in ratios.items():
            assert 0 <= info["recent_citation_ratio"] <= 1.0

    def test_case_cited_by_recent_has_high_ratio(self, sample_nodes, sample_edges):
        G = build_networkx_graph(sample_nodes, sample_edges)
        ratios = compute_rising_authority(G, recent_year_cutoff=2021)
        # 'a' cited by c(2022) and d(2023) — both recent
        assert ratios["a"]["recent_citation_ratio"] > 0.5


class TestComputeTreatmentAggregation:
    def test_aggregates_treatments(self, sample_nodes, sample_edges):
        G = build_networkx_graph(sample_nodes, sample_edges)
        treatments = compute_treatment_aggregation(G)
        assert "a" in treatments
        assert treatments["a"]["treatment_summary"]["followed"] == 1
        assert treatments["a"]["treatment_summary"]["overruled"] == 1
        assert 0 <= treatments["a"]["treatment_positive_pct"] <= 1.0

    def test_positive_pct_calculation(self, sample_nodes, sample_edges):
        G = build_networkx_graph(sample_nodes, sample_edges)
        treatments = compute_treatment_aggregation(G)
        # 'b' has affirmed(1) + distinguished(1) = 50% positive
        assert treatments["b"]["treatment_positive_pct"] == pytest.approx(0.5)
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_graph_analytics.py -v`
Expected: FAIL (ImportError — module doesn't exist yet)

**Step 3: Implement the analytics script**

Create `backend/scripts/compute_graph_analytics.py`:

```python
"""Compute graph analytics (communities, PageRank, treatment aggregation).

Run after ingestion batches:
    python -m scripts.compute_graph_analytics

Reads all Case nodes and CITES edges from Neo4j, computes analytics
using networkx, writes results back as node properties.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from datetime import datetime

import networkx as nx
from community import community_louvain  # python-louvain package

logger = logging.getLogger(__name__)

# Treatments considered "positive"
_POSITIVE_TREATMENTS = frozenset({"followed", "affirmed", "applied", "explained"})
_NEGATIVE_TREATMENTS = frozenset({"overruled", "not_followed", "per_incuriam"})


def build_networkx_graph(
    nodes: list[dict],
    edges: list[dict],
) -> nx.DiGraph:
    """Build a directed networkx graph from node/edge dicts."""
    G = nx.DiGraph()
    for node in nodes:
        G.add_node(node["id"], **{k: v for k, v in node.items() if k != "id"})
    for edge in edges:
        G.add_edge(
            edge["source"],
            edge["target"],
            treatment=edge.get("treatment"),
        )
    return G


def compute_communities(G: nx.DiGraph) -> dict[str, dict]:
    """Run Louvain community detection, return {node_id: {community_id, community_label}}."""
    # Louvain works on undirected graphs
    G_undirected = G.to_undirected()
    partition = community_louvain.best_partition(G_undirected)

    # Group nodes by community for labeling
    community_nodes: dict[int, list[str]] = {}
    for node_id, comm_id in partition.items():
        community_nodes.setdefault(comm_id, []).append(node_id)

    # Auto-label each community by most common keywords/acts_cited
    community_labels: dict[int, str] = {}
    for comm_id, node_ids in community_nodes.items():
        keyword_counter: Counter[str] = Counter()
        for nid in node_ids:
            data = G.nodes.get(nid, {})
            for field in ("keywords", "acts_cited"):
                val = data.get(field, "")
                if val:
                    for kw in str(val).split(","):
                        kw = kw.strip()
                        if kw and len(kw) > 2:
                            keyword_counter[kw] += 1
        top = keyword_counter.most_common(3)
        label = ", ".join(kw for kw, _ in top) if top else f"Cluster {comm_id}"
        community_labels[comm_id] = label

    return {
        node_id: {
            "community_id": comm_id,
            "community_label": community_labels[comm_id],
        }
        for node_id, comm_id in partition.items()
    }


def compute_pagerank(
    G: nx.DiGraph,
    *,
    communities: dict[str, dict] | None = None,
) -> dict[str, dict]:
    """Compute global + per-community PageRank, normalized to 0-100."""
    # Global PageRank
    global_pr = nx.pagerank(G, alpha=0.85)
    max_pr = max(global_pr.values()) if global_pr else 1.0

    result: dict[str, dict] = {}
    for node_id, score in global_pr.items():
        result[node_id] = {
            "pagerank_global": round((score / max_pr) * 100, 1) if max_pr > 0 else 0,
            "pagerank_community": 0.0,
        }

    # Per-community PageRank
    if communities:
        comm_groups: dict[int, list[str]] = {}
        for nid, info in communities.items():
            comm_groups.setdefault(info["community_id"], []).append(nid)

        for comm_id, node_ids in comm_groups.items():
            if len(node_ids) < 2:
                for nid in node_ids:
                    if nid in result:
                        result[nid]["pagerank_community"] = 100.0
                continue

            subgraph = G.subgraph(node_ids)
            try:
                sub_pr = nx.pagerank(subgraph, alpha=0.85)
                max_sub = max(sub_pr.values()) if sub_pr else 1.0
                for nid, score in sub_pr.items():
                    if nid in result:
                        result[nid]["pagerank_community"] = round(
                            (score / max_sub) * 100, 1
                        ) if max_sub > 0 else 0
            except nx.PowerIterationFailedConvergence:
                logger.warning("PageRank failed to converge for community %d", comm_id)

    return result


def compute_rising_authority(
    G: nx.DiGraph,
    *,
    recent_year_cutoff: int | None = None,
) -> dict[str, dict]:
    """Compute recent_citation_ratio for each node.

    Ratio = citations from cases with year >= cutoff / total citations.
    """
    if recent_year_cutoff is None:
        recent_year_cutoff = datetime.now().year - 3

    result: dict[str, dict] = {}
    for node_id in G.nodes():
        # Incoming edges = cases that cite this node
        predecessors = list(G.predecessors(node_id))
        total = len(predecessors)
        if total == 0:
            result[node_id] = {"recent_citation_ratio": 0.0}
            continue

        recent = 0
        for pred in predecessors:
            pred_year = G.nodes[pred].get("year")
            if pred_year is not None and pred_year >= recent_year_cutoff:
                recent += 1

        result[node_id] = {
            "recent_citation_ratio": round(recent / total, 3),
        }

    return result


def compute_treatment_aggregation(G: nx.DiGraph) -> dict[str, dict]:
    """Aggregate treatment counts and positive percentage for each node."""
    result: dict[str, dict] = {}

    for node_id in G.nodes():
        treatment_counts: Counter[str] = Counter()
        # Incoming edges = citations TO this node
        for pred in G.predecessors(node_id):
            edge_data = G.edges[pred, node_id]
            treatment = edge_data.get("treatment") or "cites"
            treatment_counts[treatment] += 1

        total = sum(treatment_counts.values())
        if total == 0:
            result[node_id] = {
                "treatment_positive_pct": 1.0,
                "treatment_summary": {},
            }
            continue

        positive = sum(
            count for t, count in treatment_counts.items()
            if t in _POSITIVE_TREATMENTS
        )
        result[node_id] = {
            "treatment_positive_pct": round(positive / total, 3),
            "treatment_summary": dict(treatment_counts),
        }

    return result


async def fetch_graph_data(graph_store) -> tuple[list[dict], list[dict]]:
    """Fetch all Case nodes and CITES edges from Neo4j."""
    nodes_result = await graph_store.query(
        cypher=(
            "MATCH (n:Case) "
            "RETURN n.id AS id, n.year AS year, n.cited_by_count AS cited_by_count, "
            "  n.keywords AS keywords, n.acts_cited AS acts_cited, "
            "  n.title AS title, n.citation AS citation, n.court AS court, "
            "  n.bench_type AS bench_type, n.case_type AS case_type"
        )
    )
    edges_result = await graph_store.query(
        cypher=(
            "MATCH (a:Case)-[r:CITES]->(b:Case) "
            "RETURN a.id AS source, b.id AS target, r.treatment AS treatment"
        )
    )
    return nodes_result, edges_result


async def write_analytics_to_neo4j(
    graph_store,
    *,
    communities: dict[str, dict],
    pagerank: dict[str, dict],
    rising: dict[str, dict],
    treatments: dict[str, dict],
) -> int:
    """Write computed analytics back to Neo4j as node properties."""
    # Merge all analytics per node
    all_nodes: set[str] = set(communities) | set(pagerank) | set(rising) | set(treatments)
    batch: list[dict] = []

    for node_id in all_nodes:
        props: dict = {"id": node_id}
        if node_id in communities:
            props.update(communities[node_id])
        if node_id in pagerank:
            props.update(pagerank[node_id])
        if node_id in rising:
            props.update(rising[node_id])
        if node_id in treatments:
            props["treatment_positive_pct"] = treatments[node_id]["treatment_positive_pct"]
            props["treatment_summary"] = json.dumps(treatments[node_id]["treatment_summary"])
        batch.append(props)

    # Write in batches of 500
    written = 0
    for i in range(0, len(batch), 500):
        chunk = batch[i : i + 500]
        await graph_store.query(
            cypher=(
                "UNWIND $batch AS props "
                "MATCH (c:Case {id: props.id}) "
                "SET c.community_id = props.community_id, "
                "    c.community_label = props.community_label, "
                "    c.pagerank_global = props.pagerank_global, "
                "    c.pagerank_community = props.pagerank_community, "
                "    c.recent_citation_ratio = props.recent_citation_ratio, "
                "    c.treatment_positive_pct = props.treatment_positive_pct, "
                "    c.treatment_summary = props.treatment_summary"
            ),
            params={"batch": chunk},
        )
        written += len(chunk)
        logger.info("Wrote analytics for %d/%d nodes", written, len(batch))

    return written


async def invalidate_caches(redis_client) -> None:
    """Clear Redis caches so fresh data is served."""
    keys = ["graph:stats", "graph:dashboard", "graph:communities"]
    for key in keys:
        try:
            await redis_client.delete(key)
        except Exception:
            pass


async def run_analytics(graph_store, redis_client=None) -> None:
    """Main entry point: fetch data, compute analytics, write back."""
    logger.info("Fetching graph data from Neo4j...")
    nodes, edges = await fetch_graph_data(graph_store)
    logger.info("Loaded %d nodes and %d edges", len(nodes), len(edges))

    if not nodes:
        logger.warning("No nodes found — skipping analytics")
        return

    logger.info("Building networkx graph...")
    G = build_networkx_graph(nodes, edges)

    logger.info("Computing Louvain communities...")
    communities = compute_communities(G)
    n_communities = len(set(c["community_id"] for c in communities.values()))
    logger.info("Found %d communities", n_communities)

    logger.info("Computing PageRank (global + per-community)...")
    pagerank = compute_pagerank(G, communities=communities)

    logger.info("Computing rising authority ratios...")
    rising = compute_rising_authority(G)

    logger.info("Computing treatment aggregations...")
    treatments = compute_treatment_aggregation(G)

    logger.info("Writing analytics to Neo4j...")
    written = await write_analytics_to_neo4j(
        graph_store,
        communities=communities,
        pagerank=pagerank,
        rising=rising,
        treatments=treatments,
    )
    logger.info("Wrote analytics for %d nodes", written)

    if redis_client is not None:
        logger.info("Invalidating Redis caches...")
        await invalidate_caches(redis_client)

    logger.info("Analytics computation complete!")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")

    from app.core.dependencies import get_graph_store
    from app.db.redis_client import get_redis

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    async def main():
        graph_store = get_graph_store()
        redis_client = await get_redis()
        await run_analytics(graph_store, redis_client)

    asyncio.run(main())
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_graph_analytics.py -v`
Expected: PASS

**Step 5: Add python-louvain to dependencies**

In `backend/pyproject.toml`, add `python-louvain>=0.16` to dependencies. (networkx is already a dependency.)

**Step 6: Commit**

```bash
git add backend/scripts/compute_graph_analytics.py backend/tests/unit/test_graph_analytics.py backend/pyproject.toml
git commit -m "feat(graph-v2): add analytics computation script (communities, pagerank, treatment)"
```

---

## Task 3: New Backend API Endpoints — Dashboard, Communities, Treatment Summary, Path

**Files:**
- Modify: `backend/app/core/graph/traversal.py` (add 4 new functions)
- Modify: `backend/app/api/routes/graph.py` (add 4 new routes)
- Modify: `backend/tests/unit/test_graph_traversal.py` (add tests)
- Modify: `backend/tests/unit/test_graph_routes.py` (add tests)

**Step 1: Write tests for new traversal functions**

Add to `backend/tests/unit/test_graph_traversal.py`:

```python
class TestGetDashboard:
    @pytest.mark.asyncio
    async def test_returns_most_cited(self, mock_graph_store):
        mock_graph_store.query = AsyncMock(side_effect=[
            # most_cited query
            [{"id": "a", "title": "Case A", "citation": "2020 SCC 1", "cited_by_count": 50,
              "pagerank_global": 95.0, "community_label": "Constitutional", "community_id": 1,
              "year": 2020, "court": "SC", "treatment_positive_pct": 0.9,
              "treatment_summary": '{"followed": 40, "distinguished": 5}',
              "recent_citation_ratio": 0.6, "bench_type": "constitution",
              "case_type": "Writ Petition", "pagerank_community": 98.0, "ratio": "test ratio"}],
            # rising query
            [{"id": "b", "title": "Case B", "citation": "2022 SCC 5", "cited_by_count": 10,
              "pagerank_global": 60.0, "community_label": "Criminal", "community_id": 2,
              "year": 2022, "court": "SC", "treatment_positive_pct": 1.0,
              "treatment_summary": '{"followed": 8}',
              "recent_citation_ratio": 0.8, "bench_type": "division",
              "case_type": "Criminal Appeal", "pagerank_community": 75.0, "ratio": None}],
            # recently_negative query
            [{"id": "c", "title": "Case C", "citation": "2015 SCC 3", "cited_by_count": 20,
              "pagerank_global": 40.0, "community_label": "Civil", "community_id": 3,
              "year": 2015, "court": "SC", "treatment_positive_pct": 0.3,
              "treatment_summary": '{"overruled": 2}',
              "recent_citation_ratio": 0.1, "bench_type": "single",
              "case_type": "Civil Appeal", "pagerank_community": 50.0, "ratio": None,
              "negative_treatment": "overruled", "by_case_title": "Case D", "by_case_year": 2024}],
            # communities query
            [{"community_id": 1, "community_label": "Constitutional", "case_count": 500},
             {"community_id": 2, "community_label": "Criminal", "case_count": 300}],
        ])
        result = await get_dashboard(graph_store=mock_graph_store)
        assert "most_cited" in result
        assert "rising" in result
        assert "recently_negative" in result
        assert "communities" in result
        assert len(result["most_cited"]) == 1
        assert result["most_cited"][0]["id"] == "a"

    @pytest.mark.asyncio
    async def test_filters_by_community(self, mock_graph_store):
        mock_graph_store.query = AsyncMock(return_value=[])
        result = await get_dashboard(graph_store=mock_graph_store, community_id=1)
        # Verify community filter was passed in queries
        calls = mock_graph_store.query.call_args_list
        for call in calls[:3]:  # first 3 queries should have community filter
            assert "community_id" in (call.kwargs.get("params") or {}) or \
                   "community_id" in call.kwargs.get("cypher", "")


class TestGetShortestPath:
    @pytest.mark.asyncio
    async def test_finds_path(self, mock_graph_store):
        mock_graph_store.query = AsyncMock(return_value=[
            {"path_nodes": ["a", "b", "c"], "path_rels": [{"treatment": "followed"}, {"treatment": "affirmed"}]},
        ])
        mock_graph_store.get_node = AsyncMock(side_effect=[
            {"id": "a", "title": "Case A", "year": 2020},
            {"id": "c", "title": "Case C", "year": 2022},
        ])
        result = await get_shortest_path("a", "c", graph_store=mock_graph_store)
        assert "paths" in result
        assert "from_case" in result
        assert "to_case" in result

    @pytest.mark.asyncio
    async def test_no_path_returns_empty(self, mock_graph_store):
        mock_graph_store.query = AsyncMock(return_value=[])
        mock_graph_store.get_node = AsyncMock(side_effect=[
            {"id": "a", "title": "Case A"},
            {"id": "c", "title": "Case C"},
        ])
        result = await get_shortest_path("a", "c", graph_store=mock_graph_store)
        assert result["paths"] == []


class TestGetTreatmentSummary:
    @pytest.mark.asyncio
    async def test_returns_treatment_breakdown(self, mock_graph_store):
        mock_graph_store.query = AsyncMock(return_value=[
            {"treatment": "followed", "count": 30, "citing_id": "x", "citing_title": "Case X", "citing_year": 2023},
            {"treatment": "distinguished", "count": 5, "citing_id": "y", "citing_title": "Case Y", "citing_year": 2024},
        ])
        mock_graph_store.get_node = AsyncMock(return_value={
            "id": "a", "title": "Case A", "treatment_positive_pct": 0.85,
            "treatment_summary": '{"followed": 30, "distinguished": 5}',
        })
        result = await get_treatment_summary("a", graph_store=mock_graph_store)
        assert "treatment_positive_pct" in result
        assert "breakdown" in result
        assert "verdict" in result
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_graph_traversal.py -k "Dashboard or ShortestPath or TreatmentSummary" -v`
Expected: FAIL (functions not defined)

**Step 3: Implement new traversal functions**

Add to `backend/app/core/graph/traversal.py` after `get_graph_stats()`:

```python
async def get_dashboard(
    *,
    graph_store: GraphStore,
    redis_client=None,
    community_id: int | None = None,
    limit: int = 10,
) -> dict:
    """Get dashboard data: most-cited, rising, recently negative, communities."""
    cache_key = f"graph:dashboard:{community_id or 'all'}"

    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception:
            pass

    community_filter = ""
    params: dict = {"limit": limit}
    if community_id is not None:
        community_filter = "AND n.community_id = $community_id "
        params["community_id"] = community_id

    # Most cited by PageRank
    most_cited = await graph_store.query(
        cypher=(
            f"MATCH (n:Case) WHERE n.pagerank_global IS NOT NULL {community_filter}"
            "RETURN n.id AS id, n.title AS title, n.citation AS citation, "
            "  n.cited_by_count AS cited_by_count, n.pagerank_global AS pagerank_global, "
            "  n.pagerank_community AS pagerank_community, n.community_label AS community_label, "
            "  n.community_id AS community_id, n.year AS year, n.court AS court, "
            "  n.treatment_positive_pct AS treatment_positive_pct, "
            "  n.treatment_summary AS treatment_summary, "
            "  n.recent_citation_ratio AS recent_citation_ratio, "
            "  n.bench_type AS bench_type, n.case_type AS case_type, "
            "  n.ratio AS ratio "
            "ORDER BY n.pagerank_global DESC LIMIT $limit"
        ),
        params=params,
    )

    # Rising: high recent_citation_ratio, minimum citations
    rising_params = {**params, "min_citations": 5, "min_ratio": 0.4}
    rising = await graph_store.query(
        cypher=(
            f"MATCH (n:Case) WHERE n.recent_citation_ratio >= $min_ratio "
            f"AND n.cited_by_count >= $min_citations {community_filter}"
            "RETURN n.id AS id, n.title AS title, n.citation AS citation, "
            "  n.cited_by_count AS cited_by_count, n.pagerank_global AS pagerank_global, "
            "  n.pagerank_community AS pagerank_community, n.community_label AS community_label, "
            "  n.community_id AS community_id, n.year AS year, n.court AS court, "
            "  n.treatment_positive_pct AS treatment_positive_pct, "
            "  n.treatment_summary AS treatment_summary, "
            "  n.recent_citation_ratio AS recent_citation_ratio, "
            "  n.bench_type AS bench_type, n.case_type AS case_type, "
            "  n.ratio AS ratio "
            "ORDER BY n.recent_citation_ratio DESC, n.cited_by_count DESC LIMIT $limit"
        ),
        params=rising_params,
    )

    # Recently overruled/distinguished
    recently_negative = await graph_store.query(
        cypher=(
            "MATCH (citing:Case)-[r:CITES]->(cited:Case) "
            "WHERE r.treatment IN ['overruled', 'not_followed', 'per_incuriam', 'distinguished'] "
            f"{'AND cited.community_id = $community_id ' if community_id is not None else ''}"
            "RETURN cited.id AS id, cited.title AS title, cited.citation AS citation, "
            "  cited.cited_by_count AS cited_by_count, cited.pagerank_global AS pagerank_global, "
            "  cited.pagerank_community AS pagerank_community, cited.community_label AS community_label, "
            "  cited.community_id AS community_id, cited.year AS year, cited.court AS court, "
            "  cited.treatment_positive_pct AS treatment_positive_pct, "
            "  cited.treatment_summary AS treatment_summary, "
            "  cited.recent_citation_ratio AS recent_citation_ratio, "
            "  cited.bench_type AS bench_type, cited.case_type AS case_type, "
            "  cited.ratio AS ratio, "
            "  r.treatment AS negative_treatment, "
            "  citing.title AS by_case_title, citing.year AS by_case_year "
            "ORDER BY citing.year DESC LIMIT $limit"
        ),
        params=params,
    )

    # Community list
    communities = await graph_store.query(
        cypher=(
            "MATCH (n:Case) WHERE n.community_id IS NOT NULL "
            "RETURN n.community_id AS community_id, n.community_label AS community_label, "
            "  count(n) AS case_count "
            "ORDER BY case_count DESC"
        ),
    )

    dashboard = {
        "most_cited": most_cited,
        "rising": rising,
        "recently_negative": [
            {
                "case": {k: r[k] for k in r if k not in ("negative_treatment", "by_case_title", "by_case_year")},
                "negative_treatment": r["negative_treatment"],
                "by_case_title": r.get("by_case_title"),
                "by_case_year": r.get("by_case_year"),
            }
            for r in recently_negative
        ],
        "communities": communities,
    }

    if redis_client is not None:
        try:
            await redis_client.setex(cache_key, 3600, json.dumps(dashboard))
        except Exception:
            pass

    return dashboard


async def get_shortest_path(
    from_id: str,
    to_id: str,
    *,
    graph_store: GraphStore,
    max_depth: int = 6,
) -> dict:
    """Find shortest citation paths between two cases."""
    from_node = await graph_store.get_node(from_id)
    to_node = await graph_store.get_node(to_id)

    if not from_node or not to_node:
        return {"paths": [], "from_case": from_node, "to_case": to_node, "error": "One or both cases not found in graph"}

    records = await graph_store.query(
        cypher=(
            "MATCH path = shortestPath((a:Case {id: $from_id})-[:CITES*1.."
            + str(min(max_depth, 10))
            + "]->(b:Case {id: $to_id})) "
            "RETURN [n IN nodes(path) | n.id] AS node_ids, "
            "  [r IN relationships(path) | {treatment: r.treatment, context: r.context}] AS rels"
        ),
        params={"from_id": from_id, "to_id": to_id},
    )

    # Also try reverse direction
    reverse_records = await graph_store.query(
        cypher=(
            "MATCH path = shortestPath((a:Case {id: $to_id})-[:CITES*1.."
            + str(min(max_depth, 10))
            + "]->(b:Case {id: $from_id})) "
            "RETURN [n IN nodes(path) | n.id] AS node_ids, "
            "  [r IN relationships(path) | {treatment: r.treatment, context: r.context}] AS rels"
        ),
        params={"from_id": from_id, "to_id": to_id},
    )

    all_records = records + reverse_records

    paths = []
    for rec in all_records:
        node_ids = rec["node_ids"]
        rels = rec["rels"]
        # Fetch full node data for each node in path
        nodes = []
        for nid in node_ids:
            node_data = await graph_store.get_node(nid)
            if node_data:
                nodes.append(node_data)

        edges = []
        for i, rel in enumerate(rels):
            if i < len(node_ids) - 1:
                edges.append({
                    "from": node_ids[i],
                    "to": node_ids[i + 1],
                    "type": rel.get("treatment") or "cites",
                    "context": rel.get("context"),
                })

        paths.append({"nodes": nodes, "edges": edges})

    return {
        "paths": paths,
        "from_case": from_node,
        "to_case": to_node,
    }


async def get_treatment_summary(
    case_id: str,
    *,
    graph_store: GraphStore,
    redis_client=None,
) -> dict:
    """Get detailed treatment summary for a case."""
    cache_key = f"graph:treatment:{case_id}"

    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception:
            pass

    node = await graph_store.get_node(case_id)
    if not node:
        return {"error": "Case not found in graph"}

    # Get treatment breakdown with citing case details
    citing_cases = await graph_store.query(
        cypher=(
            "MATCH (citing:Case)-[r:CITES]->(cited:Case {id: $case_id}) "
            "RETURN r.treatment AS treatment, citing.id AS citing_id, "
            "  citing.title AS citing_title, citing.year AS citing_year, "
            "  citing.citation AS citing_citation, r.context AS context "
            "ORDER BY citing.year DESC"
        ),
        params={"case_id": case_id},
    )

    # Aggregate by treatment type
    breakdown: dict[str, list] = {}
    for rec in citing_cases:
        treatment = rec.get("treatment") or "cites"
        breakdown.setdefault(treatment, []).append({
            "id": rec["citing_id"],
            "title": rec.get("citing_title"),
            "year": rec.get("citing_year"),
            "citation": rec.get("citing_citation"),
            "context": rec.get("context"),
        })

    treatment_positive_pct = node.get("treatment_positive_pct", 1.0) or 1.0
    total_citations = sum(len(v) for v in breakdown.values())

    # Determine verdict
    if any(t in breakdown for t in ("overruled", "per_incuriam")):
        verdict = "Overruled"
    elif treatment_positive_pct < 0.5:
        verdict = "Cautionary"
    elif treatment_positive_pct >= 0.8:
        verdict = "Followed"
    else:
        verdict = "Mixed"

    result = {
        "case_id": case_id,
        "treatment_positive_pct": treatment_positive_pct,
        "verdict": verdict,
        "total_citations": total_citations,
        "breakdown": breakdown,
    }

    if redis_client is not None:
        try:
            await redis_client.setex(cache_key, 900, json.dumps(result))
        except Exception:
            pass

    return result
```

**Step 4: Add new route handlers**

Add to `backend/app/api/routes/graph.py`:

```python
# At top, add imports
from app.core.graph.traversal import (
    get_authorities,
    get_citation_chain,
    get_dashboard,
    get_graph_stats,
    get_neighborhood,
    get_shortest_path,
    get_treatment_summary,
)


# After existing routes:

@router.get("/dashboard", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def dashboard(
    community_id: int | None = Query(None, description="Filter by community ID"),
    limit: int = Query(10, ge=1, le=20),
    _current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> dict:
    """Dashboard data: most-cited, rising, recently overruled, communities."""
    graph = get_graph_store()
    redis_client = await get_redis()
    try:
        return await get_dashboard(
            graph_store=graph, redis_client=redis_client,
            community_id=community_id, limit=limit,
        )
    except (ConnectionError, RuntimeError) as exc:
        logger.warning("Graph service unavailable: %s", exc)
        raise HTTPException(status_code=502, detail="Citation graph temporarily unavailable")


@router.get("/path", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def path(
    from_id: str = Query(..., description="Source case ID"),
    to_id: str = Query(..., description="Target case ID"),
    _current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> dict:
    """Find shortest citation paths between two cases."""
    graph = get_graph_store()
    try:
        return await get_shortest_path(from_id, to_id, graph_store=graph)
    except (ConnectionError, RuntimeError) as exc:
        logger.warning("Graph service unavailable: %s", exc)
        raise HTTPException(status_code=502, detail="Citation graph temporarily unavailable")


@router.get("/{case_id}/treatment-summary", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def treatment_summary(
    case_id: str,
    _current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> dict:
    """Detailed treatment summary for a case."""
    graph = get_graph_store()
    redis_client = await get_redis()
    try:
        return await get_treatment_summary(case_id, graph_store=graph, redis_client=redis_client)
    except (ConnectionError, RuntimeError) as exc:
        logger.warning("Graph service unavailable: %s", exc)
        raise HTTPException(status_code=502, detail="Citation graph temporarily unavailable")
```

**Step 5: Run all graph tests**

Run: `cd backend && python -m pytest tests/unit/test_graph_traversal.py tests/unit/test_graph_routes.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/app/core/graph/traversal.py backend/app/api/routes/graph.py backend/tests/unit/test_graph_traversal.py backend/tests/unit/test_graph_routes.py
git commit -m "feat(graph-v2): add dashboard, path, treatment-summary API endpoints"
```

---

## Task 4: Enhance Existing Graph Responses with Analytics Fields

**Files:**
- Modify: `backend/app/core/graph/traversal.py` (neighborhood/chain node building)

**Step 1: Update node building in `get_neighborhood()` and `get_citation_chain()`**

Currently at `traversal.py:72-110`, nodes are built from Neo4j query results. The existing Cypher queries already return all node properties via `n` — we just need to ensure the new analytics properties (`pagerank_global`, `community_id`, etc.) are included when building the node dict.

Find the node-building logic in `get_neighborhood()` and `get_citation_chain()` and ensure these properties are passed through. The Neo4j `get_node()` call already returns all properties, so the new properties will flow through automatically once they exist on the nodes.

**Step 2: Verify with existing tests**

Run: `cd backend && python -m pytest tests/unit/test_graph_traversal.py -v`
Expected: PASS (existing tests should not break)

**Step 3: Commit**

```bash
git add backend/app/core/graph/traversal.py
git commit -m "feat(graph-v2): pass analytics properties through neighborhood/chain responses"
```

---

## Task 5: Frontend API Client — New Endpoints

**Files:**
- Modify: `frontend/src/lib/api.ts` (add new API functions after line 665)

**Step 1: Add new API functions**

Add to `frontend/src/lib/api.ts` after the existing graph functions:

```typescript
export async function getGraphDashboard(communityId?: number, limit = 10): Promise<DashboardData> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (communityId !== undefined) params.set("community_id", String(communityId));
    return apiFetch<DashboardData>(`/graph/dashboard?${params}`);
}

export async function getGraphPath(fromId: string, toId: string): Promise<PathResult> {
    const params = new URLSearchParams({ from_id: fromId, to_id: toId });
    return apiFetch<PathResult>(`/graph/path?${params}`);
}

export async function getGraphTreatmentSummary(caseId: string): Promise<{
    case_id: string;
    treatment_positive_pct: number;
    verdict: string;
    total_citations: number;
    breakdown: Record<string, Array<{
        id: string;
        title: string | null;
        year: number | null;
        citation: string | null;
        context: string | null;
    }>>;
}> {
    return apiFetch(`/graph/${caseId}/treatment-summary`);
}
```

**Step 2: Verify types compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

**Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(graph-v2): add dashboard, path, treatment-summary API client functions"
```

---

## Task 6: Frontend — Dashboard Component

**Files:**
- Create: `frontend/src/components/graph/GraphDashboard.tsx`

**Step 1: Create the dashboard component**

This component renders the three-column dashboard (Most Cited, Rising, Recently Overruled) with topic filter pills. It receives `DashboardData` from the parent page and calls back when a case or community is selected.

```typescript
"use client";

import { useState } from "react";
import type { DashboardData, GraphNode } from "@/lib/types";

interface GraphDashboardProps {
    data: DashboardData | null;
    loading: boolean;
    selectedCommunity: number | null;
    onSelectCommunity: (id: number | null) => void;
    onSelectCase: (caseId: string) => void;
    stats: { total_judgments: number; total_edges: number } | null;
}

function TreatmentBadge({ pct }: { pct: number | null }) {
    if (pct === null) return null;
    const color = pct >= 0.8 ? "bg-green-100 text-green-800" :
                  pct >= 0.5 ? "bg-amber-100 text-amber-800" :
                  "bg-red-100 text-red-800";
    const label = pct >= 0.8 ? "Followed" : pct >= 0.5 ? "Mixed" : "Cautionary";
    return <span className={`text-xs px-2 py-0.5 rounded-full ${color}`}>{label}</span>;
}

function AuthorityScore({ score }: { score: number | null }) {
    if (score === null) return null;
    return (
        <span className="text-xs font-semibold text-stone-600">
            ★ {Math.round(score)}
        </span>
    );
}

function CaseCard({ node, onClick, extra }: {
    node: GraphNode;
    onClick: () => void;
    extra?: React.ReactNode;
}) {
    return (
        <button
            onClick={onClick}
            className="w-full text-left p-3 rounded-lg border border-stone-200 hover:border-stone-400 hover:bg-stone-50 transition-colors"
        >
            <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-stone-900 truncate">
                        {node.title || "Untitled"}
                    </p>
                    <p className="text-xs text-stone-500 mt-0.5">
                        {node.citation || "No citation"}
                        {node.year ? ` (${node.year})` : ""}
                    </p>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                    <AuthorityScore score={node.pagerank_global} />
                    <TreatmentBadge pct={node.treatment_positive_pct} />
                </div>
            </div>
            {extra}
        </button>
    );
}

export default function GraphDashboard({
    data, loading, selectedCommunity, onSelectCommunity, onSelectCase, stats,
}: GraphDashboardProps) {
    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <div className="animate-spin h-8 w-8 border-2 border-stone-300 border-t-stone-700 rounded-full" />
            </div>
        );
    }

    if (!data) {
        return (
            <div className="text-center py-20 text-stone-500">
                Failed to load dashboard data.
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Topic filter pills */}
            <div className="flex flex-wrap gap-2">
                <button
                    onClick={() => onSelectCommunity(null)}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                        selectedCommunity === null
                            ? "bg-stone-800 text-white"
                            : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                    }`}
                >
                    All Topics
                </button>
                {data.communities.map((c) => (
                    <button
                        key={c.id}
                        onClick={() => onSelectCommunity(c.id)}
                        className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                            selectedCommunity === c.id
                                ? "bg-stone-800 text-white"
                                : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                        }`}
                    >
                        {c.label}
                        <span className="ml-1 text-xs opacity-60">({c.case_count})</span>
                    </button>
                ))}
            </div>

            {/* Three columns */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Most Cited Authorities */}
                <div>
                    <h3 className="text-sm font-semibold text-stone-700 mb-3 uppercase tracking-wide">
                        Most Cited Authorities
                    </h3>
                    <div className="space-y-2">
                        {data.most_cited.length === 0 ? (
                            <p className="text-sm text-stone-400 py-4 text-center">No data yet</p>
                        ) : (
                            data.most_cited.map((node) => (
                                <CaseCard key={node.id} node={node} onClick={() => onSelectCase(node.id)} />
                            ))
                        )}
                    </div>
                </div>

                {/* Rising Authorities */}
                <div>
                    <h3 className="text-sm font-semibold text-stone-700 mb-3 uppercase tracking-wide">
                        Rising Authorities
                    </h3>
                    <div className="space-y-2">
                        {data.rising.length === 0 ? (
                            <p className="text-sm text-stone-400 py-4 text-center">No rising cases</p>
                        ) : (
                            data.rising.map((node) => (
                                <CaseCard
                                    key={node.id}
                                    node={node}
                                    onClick={() => onSelectCase(node.id)}
                                    extra={
                                        node.recent_citation_ratio !== null && (
                                            <p className="text-xs text-blue-600 mt-1">
                                                ↑ {Math.round(node.recent_citation_ratio * 100)}% citations from recent cases
                                            </p>
                                        )
                                    }
                                />
                            ))
                        )}
                    </div>
                </div>

                {/* Recently Overruled/Distinguished */}
                <div>
                    <h3 className="text-sm font-semibold text-stone-700 mb-3 uppercase tracking-wide">
                        Recently Overruled / Distinguished
                    </h3>
                    <div className="space-y-2">
                        {data.recently_negative.length === 0 ? (
                            <p className="text-sm text-stone-400 py-4 text-center">No negative treatments</p>
                        ) : (
                            data.recently_negative.map((item) => (
                                <CaseCard
                                    key={item.case.id}
                                    node={item.case}
                                    onClick={() => onSelectCase(item.case.id)}
                                    extra={
                                        <p className="text-xs text-red-600 mt-1">
                                            {item.negative_treatment} by {item.by_case_title || "unknown"}
                                            {item.by_case_year ? ` (${item.by_case_year})` : ""}
                                        </p>
                                    }
                                />
                            ))
                        )}
                    </div>
                </div>
            </div>

            {/* Stats footer */}
            {stats && (
                <div className="text-center text-sm text-stone-400 pt-4 border-t border-stone-100">
                    {stats.total_judgments.toLocaleString()} judgments · {stats.total_edges.toLocaleString()} citations
                </div>
            )}
        </div>
    );
}
```

**Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

**Step 3: Commit**

```bash
git add frontend/src/components/graph/GraphDashboard.tsx
git commit -m "feat(graph-v2): add GraphDashboard component with 3-column layout"
```

---

## Task 7: Frontend — Timeline View Component

**Files:**
- Create: `frontend/src/components/graph/TimelineView.tsx`

**Step 1: Create the timeline visualization**

This renders a D3-based scatter plot: X = judgment date, Y = authority score. Nodes are circles sized by citation count, colored by treatment. Edges are drawn as curved lines between nodes.

Use `d3` for scales, axes, and zoom. Render on a `<canvas>` for performance. The component receives `GraphData` (nodes + edges) and callbacks for node click/hover.

```typescript
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { GraphNode, GraphEdge } from "@/lib/types";

interface TimelineViewProps {
    nodes: GraphNode[];
    edges: GraphEdge[];
    queryCaseId: string | null;
    selectedNodeId: string | null;
    onNodeClick: (node: GraphNode) => void;
    onNodeHover: (node: GraphNode | null) => void;
}

// Treatment-based node colors relative to the query case
function getNodeColor(node: GraphNode, queryCaseId: string | null, edges: GraphEdge[]): string {
    if (node.id === queryCaseId) return "#B89B6A"; // gold - query node

    // Find edge between query and this node
    const edge = edges.find(
        (e) => (e.from === queryCaseId && e.to === node.id) ||
               (e.from === node.id && e.to === queryCaseId)
    );

    if (!edge) return "#6B7280"; // gray - no direct relationship

    const treatment = edge.type;
    if (["overrules", "not_followed", "per_incuriam"].includes(treatment)) return "#EF4444"; // red
    if (["distinguishes"].includes(treatment)) return "#F97316"; // orange
    if (["affirms", "followed"].includes(treatment)) return "#22C55E"; // green
    return "#6B7280"; // gray default
}

function getNodeRadius(citedByCount: number): number {
    return Math.max(4, Math.min(20, 4 + Math.log2(Math.max(1, citedByCount)) * 2));
}

export default function TimelineView({
    nodes, edges, queryCaseId, selectedNodeId, onNodeClick, onNodeHover,
}: TimelineViewProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 800, height: 500 });
    const [tooltip, setTooltip] = useState<{ x: number; y: number; node: GraphNode } | null>(null);
    const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 });

    // Compute layout positions
    const padding = { top: 40, right: 40, bottom: 50, left: 60 };

    const years = nodes.map((n) => n.year).filter((y): y is number => y !== null);
    const minYear = Math.min(...years, 1950);
    const maxYear = Math.max(...years, 2026);

    const scores = nodes.map((n) => n.pagerank_global ?? n.cited_by_count ?? 0);
    const maxScore = Math.max(...scores, 1);

    const nodePositions = new Map<string, { x: number; y: number }>();
    for (const node of nodes) {
        const year = node.year ?? minYear;
        const score = node.pagerank_global ?? node.cited_by_count ?? 0;
        const x = padding.left + ((year - minYear) / (maxYear - minYear + 1)) * (dimensions.width - padding.left - padding.right);
        const y = dimensions.height - padding.bottom - ((score / maxScore) * (dimensions.height - padding.top - padding.bottom));
        nodePositions.set(node.id, { x, y });
    }

    // Resize observer
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;
        const observer = new ResizeObserver((entries) => {
            const entry = entries[0];
            if (entry) {
                setDimensions({
                    width: entry.contentRect.width,
                    height: Math.max(400, entry.contentRect.height),
                });
            }
        });
        observer.observe(container);
        return () => observer.disconnect();
    }, []);

    // Draw canvas
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = dimensions.width * dpr;
        canvas.height = dimensions.height * dpr;
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, dimensions.width, dimensions.height);

        ctx.save();
        ctx.translate(transform.x, transform.y);
        ctx.scale(transform.k, transform.k);

        // Draw axes
        ctx.strokeStyle = "#E5E7EB";
        ctx.lineWidth = 1;

        // X-axis (years)
        ctx.beginPath();
        ctx.moveTo(padding.left, dimensions.height - padding.bottom);
        ctx.lineTo(dimensions.width - padding.right, dimensions.height - padding.bottom);
        ctx.stroke();

        // Y-axis
        ctx.beginPath();
        ctx.moveTo(padding.left, padding.top);
        ctx.lineTo(padding.left, dimensions.height - padding.bottom);
        ctx.stroke();

        // X-axis labels (years)
        ctx.fillStyle = "#9CA3AF";
        ctx.font = "11px system-ui";
        ctx.textAlign = "center";
        const yearStep = Math.max(1, Math.ceil((maxYear - minYear) / 10));
        for (let y = minYear; y <= maxYear; y += yearStep) {
            const x = padding.left + ((y - minYear) / (maxYear - minYear + 1)) * (dimensions.width - padding.left - padding.right);
            ctx.fillText(String(y), x, dimensions.height - padding.bottom + 18);
        }

        // Y-axis label
        ctx.save();
        ctx.translate(15, dimensions.height / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText("Authority Score", 0, 0);
        ctx.restore();

        // Draw edges
        for (const edge of edges) {
            const from = nodePositions.get(edge.from);
            const to = nodePositions.get(edge.to);
            if (!from || !to) continue;

            const isNegative = ["overrules", "not_followed", "per_incuriam"].includes(edge.type);
            ctx.strokeStyle = isNegative ? "#EF444480" : "#9CA3AF40";
            ctx.lineWidth = isNegative ? 1.5 : 0.8;
            ctx.setLineDash(isNegative ? [4, 4] : []);

            // Curved edge
            const midX = (from.x + to.x) / 2;
            const midY = (from.y + to.y) / 2 - 20;
            ctx.beginPath();
            ctx.moveTo(from.x, from.y);
            ctx.quadraticCurveTo(midX, midY, to.x, to.y);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // Draw nodes
        for (const node of nodes) {
            const pos = nodePositions.get(node.id);
            if (!pos) continue;

            const radius = getNodeRadius(node.cited_by_count);
            const color = getNodeColor(node, queryCaseId, edges);
            const isSelected = node.id === selectedNodeId;

            ctx.beginPath();
            ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();

            if (isSelected || node.id === queryCaseId) {
                ctx.strokeStyle = node.id === queryCaseId ? "#8B7355" : "#3B82F6";
                ctx.lineWidth = 2;
                ctx.stroke();
            }

            // Authority score label for larger nodes
            if (node.pagerank_global !== null && node.pagerank_global > 50 && radius > 8) {
                ctx.fillStyle = "#FFFFFF";
                ctx.font = "bold 9px system-ui";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(String(Math.round(node.pagerank_global)), pos.x, pos.y);
            }
        }

        ctx.restore();
    }, [nodes, edges, dimensions, queryCaseId, selectedNodeId, transform]);

    // Mouse interaction
    const handleMouseMove = useCallback((e: React.MouseEvent) => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const rect = canvas.getBoundingClientRect();
        const mx = (e.clientX - rect.left - transform.x) / transform.k;
        const my = (e.clientY - rect.top - transform.y) / transform.k;

        let hoveredNode: GraphNode | null = null;
        for (const node of nodes) {
            const pos = nodePositions.get(node.id);
            if (!pos) continue;
            const radius = getNodeRadius(node.cited_by_count);
            const dx = mx - pos.x;
            const dy = my - pos.y;
            if (dx * dx + dy * dy <= radius * radius) {
                hoveredNode = node;
                break;
            }
        }

        if (hoveredNode) {
            setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, node: hoveredNode });
            canvas.style.cursor = "pointer";
        } else {
            setTooltip(null);
            canvas.style.cursor = "default";
        }
        onNodeHover(hoveredNode);
    }, [nodes, nodePositions, transform, onNodeHover]);

    const handleClick = useCallback((e: React.MouseEvent) => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const rect = canvas.getBoundingClientRect();
        const mx = (e.clientX - rect.left - transform.x) / transform.k;
        const my = (e.clientY - rect.top - transform.y) / transform.k;

        for (const node of nodes) {
            const pos = nodePositions.get(node.id);
            if (!pos) continue;
            const radius = getNodeRadius(node.cited_by_count);
            const dx = mx - pos.x;
            const dy = my - pos.y;
            if (dx * dx + dy * dy <= radius * radius) {
                onNodeClick(node);
                return;
            }
        }
    }, [nodes, nodePositions, transform, onNodeClick]);

    // Wheel zoom
    const handleWheel = useCallback((e: React.WheelEvent) => {
        e.preventDefault();
        const scale = e.deltaY > 0 ? 0.9 : 1.1;
        setTransform((t) => ({
            x: t.x,
            y: t.y,
            k: Math.max(0.3, Math.min(5, t.k * scale)),
        }));
    }, []);

    return (
        <div ref={containerRef} className="relative w-full h-full min-h-[400px]">
            <canvas
                ref={canvasRef}
                style={{ width: dimensions.width, height: dimensions.height }}
                onMouseMove={handleMouseMove}
                onClick={handleClick}
                onWheel={handleWheel}
            />
            {/* Tooltip */}
            {tooltip && (
                <div
                    className="absolute pointer-events-none z-10 bg-white border border-stone-200 rounded-lg shadow-lg p-3 max-w-[250px]"
                    style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}
                >
                    <p className="text-sm font-medium text-stone-900 truncate">
                        {tooltip.node.title || "Untitled"}
                    </p>
                    <p className="text-xs text-stone-500">
                        {tooltip.node.citation} ({tooltip.node.year})
                    </p>
                    <div className="flex gap-3 mt-1">
                        {tooltip.node.pagerank_global !== null && (
                            <span className="text-xs text-stone-600">★ {Math.round(tooltip.node.pagerank_global)}</span>
                        )}
                        <span className="text-xs text-stone-600">
                            {tooltip.node.cited_by_count} citations
                        </span>
                    </div>
                </div>
            )}
        </div>
    );
}
```

**Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

**Step 3: Commit**

```bash
git add frontend/src/components/graph/TimelineView.tsx
git commit -m "feat(graph-v2): add TimelineView component with date x authority scatter plot"
```

---

## Task 8: Frontend — Case Detail Side Panel

**Files:**
- Create: `frontend/src/components/graph/CaseDetailPanel.tsx`

**Step 1: Create the side panel**

```typescript
"use client";

import { useEffect, useState } from "react";
import type { GraphNode } from "@/lib/types";
import { getGraphTreatmentSummary } from "@/lib/api";

interface CaseDetailPanelProps {
    node: GraphNode;
    onClose: () => void;
    onExplore: (caseId: string) => void;
}

const TREATMENT_COLORS: Record<string, string> = {
    followed: "bg-green-100 text-green-800",
    affirmed: "bg-green-100 text-green-800",
    applied: "bg-green-100 text-green-800",
    explained: "bg-blue-100 text-blue-800",
    distinguished: "bg-amber-100 text-amber-800",
    doubted: "bg-amber-100 text-amber-800",
    overruled: "bg-red-100 text-red-800",
    not_followed: "bg-red-100 text-red-800",
    per_incuriam: "bg-red-100 text-red-800",
    cites: "bg-stone-100 text-stone-600",
};

export default function CaseDetailPanel({ node, onClose, onExplore }: CaseDetailPanelProps) {
    const [treatmentData, setTreatmentData] = useState<{
        verdict: string;
        treatment_positive_pct: number;
        total_citations: number;
        breakdown: Record<string, Array<{ id: string; title: string | null; year: number | null }>>;
    } | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        getGraphTreatmentSummary(node.id)
            .then((data) => { if (!cancelled) setTreatmentData(data); })
            .catch(() => { /* treatment data is optional */ })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [node.id]);

    const positivePct = treatmentData?.treatment_positive_pct ?? node.treatment_positive_pct ?? 1;
    const verdict = treatmentData?.verdict ??
        (positivePct >= 0.8 ? "Followed" : positivePct >= 0.5 ? "Mixed" : "Cautionary");

    const verdictColor = verdict === "Followed" ? "text-green-700" :
                         verdict === "Overruled" ? "text-red-700" :
                         verdict === "Cautionary" ? "text-red-600" :
                         "text-amber-700";

    return (
        <div className="w-80 border-l border-stone-200 bg-white overflow-y-auto h-full">
            <div className="p-4 space-y-4">
                {/* Header */}
                <div className="flex items-start justify-between">
                    <div className="min-w-0 flex-1">
                        <h3 className="text-sm font-semibold text-stone-900">
                            {node.title || "Untitled Case"}
                        </h3>
                        <p className="text-xs text-stone-500 mt-0.5">
                            {node.citation || "No citation"}
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-stone-400 hover:text-stone-600 p-1"
                    >
                        ✕
                    </button>
                </div>

                {/* Treatment summary bar */}
                <div>
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-stone-500">Treatment</span>
                        <span className={`text-xs font-semibold ${verdictColor}`}>
                            {verdict}
                        </span>
                    </div>
                    <div className="w-full h-2 bg-stone-100 rounded-full overflow-hidden">
                        <div
                            className={`h-full rounded-full ${
                                positivePct >= 0.8 ? "bg-green-500" :
                                positivePct >= 0.5 ? "bg-amber-500" :
                                "bg-red-500"
                            }`}
                            style={{ width: `${positivePct * 100}%` }}
                        />
                    </div>
                    <p className="text-xs text-stone-400 mt-0.5">
                        {Math.round(positivePct * 100)}% positive treatment
                    </p>
                </div>

                {/* Authority scores */}
                <div className="space-y-1">
                    <h4 className="text-xs font-semibold text-stone-700 uppercase tracking-wide">Authority Score</h4>
                    {node.community_label && node.pagerank_community !== null && (
                        <div className="flex justify-between text-sm">
                            <span className="text-stone-600">{node.community_label}:</span>
                            <span className="font-semibold">{Math.round(node.pagerank_community)}/100</span>
                        </div>
                    )}
                    {node.pagerank_global !== null && (
                        <div className="flex justify-between text-sm">
                            <span className="text-stone-600">Overall:</span>
                            <span className="font-semibold">{Math.round(node.pagerank_global)}/100</span>
                        </div>
                    )}
                </div>

                {/* Metadata */}
                <div className="space-y-1 text-sm">
                    <h4 className="text-xs font-semibold text-stone-700 uppercase tracking-wide">Details</h4>
                    {node.bench_type && (
                        <div className="flex justify-between">
                            <span className="text-stone-500">Bench:</span>
                            <span className="text-stone-700">{node.bench_type}</span>
                        </div>
                    )}
                    {node.year && (
                        <div className="flex justify-between">
                            <span className="text-stone-500">Year:</span>
                            <span className="text-stone-700">{node.year}</span>
                        </div>
                    )}
                    {node.case_type && (
                        <div className="flex justify-between">
                            <span className="text-stone-500">Type:</span>
                            <span className="text-stone-700">{node.case_type}</span>
                        </div>
                    )}
                    {node.court && (
                        <div className="flex justify-between">
                            <span className="text-stone-500">Court:</span>
                            <span className="text-stone-700">{node.court}</span>
                        </div>
                    )}
                </div>

                {/* Ratio excerpt */}
                {node.ratio && (
                    <div>
                        <h4 className="text-xs font-semibold text-stone-700 uppercase tracking-wide mb-1">Ratio Decidendi</h4>
                        <p className="text-xs text-stone-600 leading-relaxed line-clamp-6">
                            {node.ratio}
                        </p>
                    </div>
                )}

                {/* Treatment breakdown */}
                {treatmentData && treatmentData.breakdown && (
                    <div>
                        <h4 className="text-xs font-semibold text-stone-700 uppercase tracking-wide mb-2">
                            Treatment Breakdown
                        </h4>
                        <div className="space-y-1">
                            {Object.entries(treatmentData.breakdown).map(([treatment, cases]) => (
                                <div key={treatment} className="flex items-center justify-between">
                                    <span className={`text-xs px-2 py-0.5 rounded-full ${TREATMENT_COLORS[treatment] || "bg-stone-100 text-stone-600"}`}>
                                        {treatment}
                                    </span>
                                    <span className="text-xs text-stone-500">{cases.length}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Action buttons */}
                <div className="flex flex-col gap-2 pt-2 border-t border-stone-100">
                    <a
                        href={`/cases/${node.id}`}
                        className="text-center text-sm py-2 px-4 rounded-lg border border-stone-300 text-stone-700 hover:bg-stone-50 transition-colors"
                    >
                        View Full Case
                    </a>
                    <button
                        onClick={() => onExplore(node.id)}
                        className="text-sm py-2 px-4 rounded-lg bg-stone-800 text-white hover:bg-stone-700 transition-colors"
                    >
                        Explore from here
                    </button>
                </div>
            </div>
        </div>
    );
}
```

**Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

**Step 3: Commit**

```bash
git add frontend/src/components/graph/CaseDetailPanel.tsx
git commit -m "feat(graph-v2): add CaseDetailPanel with treatment summary and authority scores"
```

---

## Task 9: Frontend — Enhanced Network View

**Files:**
- Create: `frontend/src/components/graph/NetworkView.tsx`

**Step 1: Extract and enhance the current force-directed graph**

Extract the ForceGraph2D code from `page.tsx` into its own component, enhanced with:
- Node coloring by treatment (green/yellow/red)
- Authority score badge on nodes
- Community cluster shading (background color)
- Edge labels on hover

```typescript
"use client";

import { useCallback, useRef } from "react";
import dynamic from "next/dynamic";
import type { GraphNode, GraphEdge } from "@/lib/types";
import { getEdgeColor } from "@/lib/graph-utils";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

interface NetworkViewProps {
    nodes: GraphNode[];
    edges: GraphEdge[];
    queryCaseId: string | null;
    selectedNodeId: string | null;
    onNodeClick: (node: GraphNode) => void;
}

// Community colors (light backgrounds)
const COMMUNITY_COLORS = [
    "#FEF3C7", "#DBEAFE", "#D1FAE5", "#FCE7F3", "#E0E7FF",
    "#FEE2E2", "#ECFCCB", "#F3E8FF", "#CFFAFE", "#FFF7ED",
];

function getNodeColor(node: GraphNode, queryCaseId: string | null): string {
    if (node.id === queryCaseId) return "#B89B6A";
    if (node.treatment_positive_pct !== null) {
        if (node.treatment_positive_pct >= 0.8) return "#22C55E";
        if (node.treatment_positive_pct >= 0.5) return "#F97316";
        return "#EF4444";
    }
    return "#6B7280";
}

export default function NetworkView({
    nodes, edges, queryCaseId, selectedNodeId, onNodeClick,
}: NetworkViewProps) {
    const graphRef = useRef<any>(null);

    const graphData = {
        nodes: nodes.map((n) => ({
            ...n,
            _color: getNodeColor(n, queryCaseId),
            _radius: Math.max(4, Math.min(20, 4 + Math.log2(Math.max(1, n.cited_by_count)) * 2)),
        })),
        links: edges.map((e) => ({
            source: e.from,
            target: e.to,
            _type: e.type,
            _color: getEdgeColor(e.type),
        })),
    };

    const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D) => {
        const radius = node._radius || 5;

        // Community background (subtle)
        if (node.community_id !== undefined && node.community_id !== null) {
            const bgColor = COMMUNITY_COLORS[node.community_id % COMMUNITY_COLORS.length];
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius + 4, 0, Math.PI * 2);
            ctx.fillStyle = bgColor + "60";
            ctx.fill();
        }

        // Main node
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = node._color;
        ctx.fill();

        // Selection ring
        if (node.id === selectedNodeId) {
            ctx.strokeStyle = "#3B82F6";
            ctx.lineWidth = 2;
            ctx.stroke();
        }

        // Authority score label
        if (node.pagerank_global !== null && node.pagerank_global > 40 && radius > 7) {
            ctx.fillStyle = "#FFFFFF";
            ctx.font = `bold ${Math.max(8, radius * 0.8)}px system-ui`;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(String(Math.round(node.pagerank_global)), node.x, node.y);
        }
    }, [selectedNodeId]);

    return (
        <div className="w-full h-full">
            <ForceGraph2D
                ref={graphRef}
                graphData={graphData}
                nodeCanvasObject={paintNode}
                nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
                    const radius = node._radius || 5;
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, radius + 2, 0, Math.PI * 2);
                    ctx.fillStyle = color;
                    ctx.fill();
                }}
                linkColor={(link: any) => link._color}
                linkDirectionalArrowLength={4}
                linkDirectionalArrowRelPos={1}
                onNodeClick={(node: any) => onNodeClick(node)}
                cooldownTicks={100}
                nodeLabel={(node: any) =>
                    `${node.title || "Untitled"}\n${node.citation || ""} (${node.year || "?"})\nAuthority: ${node.pagerank_global !== null ? Math.round(node.pagerank_global) : "N/A"}`
                }
            />
        </div>
    );
}
```

**Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

**Step 3: Commit**

```bash
git add frontend/src/components/graph/NetworkView.tsx
git commit -m "feat(graph-v2): add enhanced NetworkView with treatment colors and authority badges"
```

---

## Task 10: Frontend — Rewrite Graph Page with All Modes

**Files:**
- Modify: `frontend/src/app/graph/page.tsx` (major rewrite)

**Step 1: Rewrite the graph page**

The page now orchestrates: Dashboard (default), Timeline, Network modes with the side panel. The current 447-line page gets restructured to use the new components.

Key changes:
- Add `view` state: `"dashboard" | "timeline" | "network"`
- Dashboard loads on mount via `getGraphDashboard()`
- Selecting a case switches to timeline view and loads graph data
- Toggle between timeline and network for the graph views
- Side panel shows on node click
- Path mode available in network view

The full rewrite should:
1. Keep existing search functionality (debounced search with dropdown)
2. Replace the inline ForceGraph2D with `<NetworkView>` and `<TimelineView>` components
3. Add `<GraphDashboard>` as the default view
4. Add `<CaseDetailPanel>` sidebar
5. Add view toggle buttons (Dashboard / Timeline / Network)
6. Add Path mode search (two case inputs) in network view
7. Wire up community filter from dashboard to API calls

**Step 2: Run frontend tests**

Run: `cd frontend && npx vitest run --reporter=verbose`
Expected: PASS (or update any graph-page-specific tests)

**Step 3: Commit**

```bash
git add frontend/src/app/graph/page.tsx
git commit -m "feat(graph-v2): rewrite graph page with dashboard, timeline, network, and side panel"
```

---

## Task 11: Frontend — Path Finder Component

**Files:**
- Create: `frontend/src/components/graph/PathFinder.tsx`

**Step 1: Create path finder UI**

Two search inputs ("From case" and "To case") with the same debounced search as the main search. Shows results in the network view with only the path nodes/edges highlighted.

```typescript
"use client";

import { useCallback, useState } from "react";
import { search as searchApi } from "@/lib/api";
import { getGraphPath } from "@/lib/api";
import type { PathResult } from "@/lib/types";

interface PathFinderProps {
    onPathFound: (result: PathResult) => void;
    loading: boolean;
    setLoading: (l: boolean) => void;
}

export default function PathFinder({ onPathFound, loading, setLoading }: PathFinderProps) {
    const [fromQuery, setFromQuery] = useState("");
    const [toQuery, setToQuery] = useState("");
    const [fromResults, setFromResults] = useState<Array<{ id: string; title: string }>>([]);
    const [toResults, setToResults] = useState<Array<{ id: string; title: string }>>([]);
    const [fromId, setFromId] = useState<string | null>(null);
    const [toId, setToId] = useState<string | null>(null);
    const [fromTitle, setFromTitle] = useState("");
    const [toTitle, setToTitle] = useState("");

    const handleSearch = useCallback(async (query: string, setter: (r: any[]) => void) => {
        if (query.length < 3) { setter([]); return; }
        try {
            const res = await searchApi(query, { limit: 5 });
            setter(res.results?.map((r: any) => ({ id: r.id, title: r.title })) || []);
        } catch {
            setter([]);
        }
    }, []);

    const handleFindPath = useCallback(async () => {
        if (!fromId || !toId) return;
        setLoading(true);
        try {
            const result = await getGraphPath(fromId, toId);
            onPathFound(result);
        } catch {
            // error handled by caller
        } finally {
            setLoading(false);
        }
    }, [fromId, toId, onPathFound, setLoading]);

    return (
        <div className="flex items-end gap-3 p-3 bg-stone-50 rounded-lg border border-stone-200">
            {/* From case */}
            <div className="flex-1 relative">
                <label className="text-xs font-medium text-stone-500 mb-1 block">From case</label>
                <input
                    type="text"
                    value={fromId ? fromTitle : fromQuery}
                    onChange={(e) => { setFromQuery(e.target.value); setFromId(null); handleSearch(e.target.value, setFromResults); }}
                    placeholder="Search..."
                    className="w-full text-sm px-3 py-2 border border-stone-300 rounded-lg"
                />
                {fromResults.length > 0 && !fromId && (
                    <div className="absolute z-20 top-full mt-1 w-full bg-white border border-stone-200 rounded-lg shadow-lg max-h-40 overflow-y-auto">
                        {fromResults.map((r) => (
                            <button key={r.id} onClick={() => { setFromId(r.id); setFromTitle(r.title); setFromResults([]); }}
                                className="w-full text-left px-3 py-2 text-sm hover:bg-stone-50 truncate">{r.title}</button>
                        ))}
                    </div>
                )}
            </div>

            {/* To case */}
            <div className="flex-1 relative">
                <label className="text-xs font-medium text-stone-500 mb-1 block">To case</label>
                <input
                    type="text"
                    value={toId ? toTitle : toQuery}
                    onChange={(e) => { setToQuery(e.target.value); setToId(null); handleSearch(e.target.value, setToResults); }}
                    placeholder="Search..."
                    className="w-full text-sm px-3 py-2 border border-stone-300 rounded-lg"
                />
                {toResults.length > 0 && !toId && (
                    <div className="absolute z-20 top-full mt-1 w-full bg-white border border-stone-200 rounded-lg shadow-lg max-h-40 overflow-y-auto">
                        {toResults.map((r) => (
                            <button key={r.id} onClick={() => { setToId(r.id); setToTitle(r.title); setToResults([]); }}
                                className="w-full text-left px-3 py-2 text-sm hover:bg-stone-50 truncate">{r.title}</button>
                        ))}
                    </div>
                )}
            </div>

            <button
                onClick={handleFindPath}
                disabled={!fromId || !toId || loading}
                className="px-4 py-2 text-sm bg-stone-800 text-white rounded-lg hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            >
                {loading ? "Finding..." : "Find Path"}
            </button>
        </div>
    );
}
```

**Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

**Step 3: Commit**

```bash
git add frontend/src/components/graph/PathFinder.tsx
git commit -m "feat(graph-v2): add PathFinder component for citation path discovery"
```

---

## Task 12: Backend Tests for New Endpoints (Route-Level)

**Files:**
- Modify: `backend/tests/unit/test_graph_routes.py`

**Step 1: Add route tests**

```python
class TestDashboardRoute:
    @pytest.mark.asyncio
    async def test_dashboard_returns_200(self, client, mock_graph_store):
        mock_graph_store.query = AsyncMock(return_value=[])
        response = await client.get("/api/v1/graph/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "most_cited" in data
        assert "rising" in data
        assert "recently_negative" in data
        assert "communities" in data

    @pytest.mark.asyncio
    async def test_dashboard_with_community_filter(self, client, mock_graph_store):
        mock_graph_store.query = AsyncMock(return_value=[])
        response = await client.get("/api/v1/graph/dashboard?community_id=1")
        assert response.status_code == 200


class TestPathRoute:
    @pytest.mark.asyncio
    async def test_path_requires_both_ids(self, client, mock_graph_store):
        response = await client.get("/api/v1/graph/path?from_id=a")
        assert response.status_code == 422  # missing to_id

    @pytest.mark.asyncio
    async def test_path_returns_200(self, client, mock_graph_store):
        mock_graph_store.query = AsyncMock(return_value=[])
        mock_graph_store.get_node = AsyncMock(return_value={"id": "a", "title": "A"})
        response = await client.get("/api/v1/graph/path?from_id=a&to_id=b")
        assert response.status_code == 200


class TestTreatmentSummaryRoute:
    @pytest.mark.asyncio
    async def test_treatment_summary_returns_200(self, client, mock_graph_store):
        mock_graph_store.get_node = AsyncMock(return_value={"id": "a", "treatment_positive_pct": 0.9})
        mock_graph_store.query = AsyncMock(return_value=[])
        response = await client.get("/api/v1/graph/a/treatment-summary")
        assert response.status_code == 200
```

**Step 2: Run route tests**

Run: `cd backend && python -m pytest tests/unit/test_graph_routes.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/unit/test_graph_routes.py
git commit -m "test(graph-v2): add route tests for dashboard, path, treatment-summary endpoints"
```

---

## Task 13: Integration Testing and Final Verification

**Step 1: Run full backend test suite**

Run: `cd backend && python -m pytest tests/ -x -q --timeout=60`
Expected: PASS (all ~2185 tests)

**Step 2: Run full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: PASS (all ~311 tests)

**Step 3: Run TypeScript type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS

**Step 4: Manual smoke test**

1. Start backend: `cd backend && uvicorn app.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Visit `/graph` — should show dashboard (empty if no analytics computed yet)
4. Run analytics: `cd backend && python -m scripts.compute_graph_analytics`
5. Refresh `/graph` — should show populated dashboard
6. Click a case — should switch to timeline view
7. Toggle to network view — should show enhanced force-directed graph
8. Click a node — should open side panel with treatment data
9. Test path finder — enter two cases and find path

**Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix(graph-v2): integration fixes from smoke testing"
```

---

## Dependency Summary

**Python packages to add:**
- `python-louvain>=0.16` (Louvain community detection)
- `networkx>=3.0` (already exists)

**No new frontend packages needed** — uses existing `react-force-graph-2d` + native Canvas API.

**Infrastructure change required:** Migrate Neo4j from AuraDB Free to self-hosted Neo4j Community + GDS Community on VM. This is a prerequisite but can be done in parallel with code implementation — the code works with standard Neo4j too (analytics just use networkx).

## File Manifest

| Action | File |
|--------|------|
| Modify | `frontend/src/lib/types.ts` |
| Modify | `frontend/src/lib/api.ts` |
| Modify | `frontend/src/app/graph/page.tsx` |
| Modify | `backend/app/core/graph/traversal.py` |
| Modify | `backend/app/api/routes/graph.py` |
| Modify | `backend/pyproject.toml` |
| Create | `frontend/src/components/graph/GraphDashboard.tsx` |
| Create | `frontend/src/components/graph/TimelineView.tsx` |
| Create | `frontend/src/components/graph/CaseDetailPanel.tsx` |
| Create | `frontend/src/components/graph/NetworkView.tsx` |
| Create | `frontend/src/components/graph/PathFinder.tsx` |
| Create | `backend/scripts/compute_graph_analytics.py` |
| Create | `backend/tests/unit/test_graph_analytics.py` |
| Modify | `backend/tests/unit/test_graph_traversal.py` |
| Modify | `backend/tests/unit/test_graph_routes.py` |
