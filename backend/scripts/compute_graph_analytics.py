"""Compute graph analytics and write results back to Neo4j.

Runs Louvain community detection, PageRank, rising authority scoring,
and treatment aggregation on the citation graph. Results are stored as
node properties for fast API retrieval.

Usage: python -m scripts.compute_graph_analytics
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import community as community_louvain  # python-louvain
import networkx as nx

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.interfaces import GraphStore

logger = logging.getLogger(__name__)

POSITIVE_TREATMENTS = frozenset({"followed", "affirmed", "applied", "explained"})
NEGATIVE_TREATMENTS = frozenset({"overruled", "not_followed", "per_incuriam"})
WRITE_BATCH_SIZE = 500


# ---------------------------------------------------------------------------
# 1. Build networkx graph
# ---------------------------------------------------------------------------


def build_networkx_graph(nodes: list[dict], edges: list[dict]) -> nx.DiGraph:
    """Create a DiGraph from raw node/edge dicts exported from Neo4j."""
    G = nx.DiGraph()
    for node in nodes:
        node_id = str(node["id"])
        attrs = {k: v for k, v in node.items() if k != "id"}
        G.add_node(node_id, **attrs)
    for edge in edges:
        src = str(edge["source"])
        tgt = str(edge["target"])
        attrs = {k: v for k, v in edge.items() if k not in ("source", "target")}
        G.add_edge(src, tgt, **attrs)
    return G


# ---------------------------------------------------------------------------
# 2. Community detection (Louvain)
# ---------------------------------------------------------------------------


def _label_community(G: nx.DiGraph, member_ids: list[str]) -> str:
    """Build a human-readable label from top keywords/acts in the community."""
    keyword_counter: Counter[str] = Counter()
    for nid in member_ids:
        data = G.nodes.get(nid, {})
        for field in ("keywords", "acts_cited"):
            raw = data.get(field, "")
            if raw:
                for token in str(raw).split(","):
                    token = token.strip()
                    if token:
                        keyword_counter[token] += 1
    top = [kw for kw, _ in keyword_counter.most_common(3)]
    return ", ".join(top) if top else "Unlabeled"


def compute_communities(G: nx.DiGraph) -> dict[str, dict]:
    """Run Louvain on the undirected projection and return per-node info."""
    if len(G) == 0:
        return {}

    undirected = G.to_undirected()
    partition = community_louvain.best_partition(undirected)

    # Group members by community id
    communities_members: dict[int, list[str]] = {}
    for node_id, comm_id in partition.items():
        communities_members.setdefault(comm_id, []).append(node_id)

    # Build labels per community
    community_labels: dict[int, str] = {}
    for comm_id, members in communities_members.items():
        community_labels[comm_id] = _label_community(G, members)

    result: dict[str, dict] = {}
    for node_id, comm_id in partition.items():
        result[node_id] = {
            "community_id": comm_id,
            "community_label": community_labels[comm_id],
        }
    return result


# ---------------------------------------------------------------------------
# 3. PageRank
# ---------------------------------------------------------------------------


def compute_pagerank(
    G: nx.DiGraph,
    *,
    communities: dict[str, dict] | None = None,
) -> dict[str, dict]:
    """Compute global and per-community PageRank, normalised to 0-100."""
    if len(G) == 0:
        return {}

    # Global PageRank
    try:
        raw_pr = nx.pagerank(G, max_iter=200)
    except nx.PowerIterationFailedConvergence:
        logger.warning("PageRank did not converge; using last iteration values")
        raw_pr = nx.pagerank(G, max_iter=500, tol=1e-3)

    max_pr = max(raw_pr.values()) if raw_pr else 1.0
    if max_pr == 0:
        max_pr = 1.0

    result: dict[str, dict] = {}
    for node_id, score in raw_pr.items():
        result[node_id] = {
            "pagerank_global": round((score / max_pr) * 100, 2),
        }

    # Per-community PageRank
    if communities:
        comm_members: dict[int, list[str]] = {}
        for nid, info in communities.items():
            comm_members.setdefault(info["community_id"], []).append(nid)

        for comm_id, members in comm_members.items():
            if len(members) == 1:
                nid = members[0]
                result.setdefault(nid, {})["pagerank_community"] = 100.0
                continue

            subgraph = G.subgraph(members)
            try:
                sub_pr = nx.pagerank(subgraph, max_iter=200)
            except nx.PowerIterationFailedConvergence:
                sub_pr = nx.pagerank(subgraph, max_iter=500, tol=1e-3)

            sub_max = max(sub_pr.values()) if sub_pr else 1.0
            if sub_max == 0:
                sub_max = 1.0

            for nid, score in sub_pr.items():
                result.setdefault(nid, {})["pagerank_community"] = round(
                    (score / sub_max) * 100, 2
                )
    else:
        # No community info — set community rank equal to global
        for nid in result:
            result[nid]["pagerank_community"] = result[nid]["pagerank_global"]

    return result


# ---------------------------------------------------------------------------
# 4. Rising authority
# ---------------------------------------------------------------------------


def compute_rising_authority(
    G: nx.DiGraph,
    *,
    recent_year_cutoff: int | None = None,
) -> dict[str, dict]:
    """Compute recent_citation_ratio = citations from recent years / total."""
    if recent_year_cutoff is None:
        recent_year_cutoff = datetime.now().year - 3

    result: dict[str, dict] = {}
    for node_id in G.nodes:
        predecessors = list(G.predecessors(node_id))
        total = len(predecessors)
        if total == 0:
            result[node_id] = {"recent_citation_ratio": 0.0}
            continue

        recent = 0
        for pred in predecessors:
            pred_year = G.nodes[pred].get("year")
            if pred_year is not None and int(pred_year) >= recent_year_cutoff:
                recent += 1

        result[node_id] = {
            "recent_citation_ratio": round(recent / total, 4),
        }
    return result


# ---------------------------------------------------------------------------
# 5. Treatment aggregation
# ---------------------------------------------------------------------------


def compute_treatment_aggregation(G: nx.DiGraph) -> dict[str, dict]:
    """Aggregate treatment counts and positive percentage per node."""
    result: dict[str, dict] = {}
    for node_id in G.nodes:
        treatment_counts: Counter[str] = Counter()
        for pred in G.predecessors(node_id):
            edge_data = G.edges[pred, node_id]
            treatment = edge_data.get("treatment")
            if treatment:
                treatment_counts[treatment] += 1

        total = sum(treatment_counts.values())
        if total == 0:
            positive_pct = 1.0
        else:
            positive = sum(
                count for t, count in treatment_counts.items() if t in POSITIVE_TREATMENTS
            )
            positive_pct = round(positive / total, 4)

        result[node_id] = {
            "treatment_positive_pct": positive_pct,
            "treatment_summary": dict(treatment_counts),
        }
    return result


# ---------------------------------------------------------------------------
# 6. Fetch graph data from Neo4j
# ---------------------------------------------------------------------------


async def fetch_graph_data(graph_store: GraphStore) -> tuple[list[dict], list[dict]]:
    """Fetch all Case nodes and CITES edges from Neo4j."""
    node_records = await graph_store.query(
        """
        MATCH (c:Case)
        RETURN c.id AS id, c.year AS year, c.cited_by_count AS cited_by_count,
               c.keywords AS keywords, c.acts_cited AS acts_cited
        """,
    )
    edge_records = await graph_store.query(
        """
        MATCH (a:Case)-[r:CITES]->(b:Case)
        RETURN a.id AS source, b.id AS target, r.treatment AS treatment
        """,
    )
    nodes = [dict(r) for r in node_records]
    edges = [dict(r) for r in edge_records]
    logger.info("Fetched %d nodes and %d edges from Neo4j", len(nodes), len(edges))
    return nodes, edges


# ---------------------------------------------------------------------------
# 7. Write analytics back to Neo4j
# ---------------------------------------------------------------------------


async def write_analytics_to_neo4j(
    graph_store: GraphStore,
    *,
    communities: dict[str, dict],
    pagerank: dict[str, dict],
    rising: dict[str, dict],
    treatments: dict[str, dict],
) -> int:
    """Merge all analytics as node properties. Returns count of nodes updated."""
    # Combine all analytics per node
    all_node_ids = set(communities) | set(pagerank) | set(rising) | set(treatments)
    rows: list[dict] = []
    for nid in all_node_ids:
        row: dict = {"id": nid}
        if nid in communities:
            row["community_id"] = communities[nid].get("community_id")
            row["community_label"] = communities[nid].get("community_label")
        if nid in pagerank:
            row["pagerank_global"] = pagerank[nid].get("pagerank_global", 0.0)
            row["pagerank_community"] = pagerank[nid].get("pagerank_community", 0.0)
        if nid in rising:
            row["recent_citation_ratio"] = rising[nid].get("recent_citation_ratio", 0.0)
        if nid in treatments:
            row["treatment_positive_pct"] = treatments[nid].get("treatment_positive_pct", 1.0)
            row["treatment_summary"] = json.dumps(
                treatments[nid].get("treatment_summary", {})
            )
        rows.append(row)

    # Batch write in chunks
    total_updated = 0
    for i in range(0, len(rows), WRITE_BATCH_SIZE):
        batch = rows[i : i + WRITE_BATCH_SIZE]
        await graph_store.query(
            """
            UNWIND $rows AS row
            MATCH (c:Case {id: row.id})
            SET c.community_id = row.community_id,
                c.community_label = row.community_label,
                c.pagerank_global = row.pagerank_global,
                c.pagerank_community = row.pagerank_community,
                c.recent_citation_ratio = row.recent_citation_ratio,
                c.treatment_positive_pct = row.treatment_positive_pct,
                c.treatment_summary = row.treatment_summary
            """,
            params={"rows": batch},
        )
        total_updated += len(batch)

    logger.info("Wrote analytics for %d nodes to Neo4j", total_updated)
    return total_updated


# ---------------------------------------------------------------------------
# 8. Cache invalidation
# ---------------------------------------------------------------------------


async def invalidate_caches(redis_client: object) -> None:
    """Delete known graph analytics cache keys from Redis."""
    keys = ["graph:stats", "graph:dashboard", "graph:communities"]
    for key in keys:
        try:
            await redis_client.delete(key)  # type: ignore[union-attr]
        except Exception:
            logger.warning("Failed to delete cache key %s", key, exc_info=True)
    logger.info("Invalidated %d cache keys", len(keys))


# ---------------------------------------------------------------------------
# 9. Main orchestrator
# ---------------------------------------------------------------------------


async def run_analytics(
    graph_store: GraphStore,
    redis_client: object | None = None,
) -> None:
    """End-to-end analytics pipeline."""
    logger.info("Starting graph analytics computation")

    # Fetch
    nodes, edges = await fetch_graph_data(graph_store)
    if not nodes:
        logger.warning("No nodes found in graph — skipping analytics")
        return

    # Build networkx graph
    G = build_networkx_graph(nodes, edges)
    logger.info("Built networkx graph: %d nodes, %d edges", len(G.nodes), len(G.edges))

    # Compute
    communities = compute_communities(G)
    logger.info("Computed %d community assignments", len(communities))

    pr = compute_pagerank(G, communities=communities)
    logger.info("Computed PageRank for %d nodes", len(pr))

    rising = compute_rising_authority(G)
    logger.info("Computed rising authority for %d nodes", len(rising))

    treatments = compute_treatment_aggregation(G)
    logger.info("Computed treatment aggregation for %d nodes", len(treatments))

    # Write back
    updated = await write_analytics_to_neo4j(
        graph_store,
        communities=communities,
        pagerank=pr,
        rising=rising,
        treatments=treatments,
    )
    logger.info("Updated %d nodes with analytics", updated)

    # Invalidate caches
    if redis_client is not None:
        await invalidate_caches(redis_client)

    logger.info("Graph analytics computation complete")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    async def main() -> None:
        from app.core.providers.neo4j_graph import Neo4jGraphStore
        from app.core.config import settings

        graph_store = Neo4jGraphStore(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD,
        )
        redis_client = None
        try:
            from redis.asyncio import Redis

            redis_client = Redis.from_url(settings.REDIS_URL)
        except Exception:
            logger.warning("Redis not available — skipping cache invalidation")

        try:
            await run_analytics(graph_store, redis_client)
        finally:
            if redis_client is not None:
                await redis_client.aclose()

    asyncio.run(main())
