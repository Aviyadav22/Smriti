"""Citation graph traversal operations.

Provides functions for querying the Neo4j citation graph:
neighborhood exploration, citation chains, authority ranking, and statistics.
"""

from __future__ import annotations

import logging

from app.core.interfaces import GraphStore

logger = logging.getLogger(__name__)

MAX_NODES = 200


async def get_neighborhood(
    case_id: str,
    *,
    graph_store: GraphStore,
    depth: int = 1,
) -> dict:
    """Get the citation neighborhood around a case.

    Returns nodes and edges within ``depth`` hops of the given case,
    capped at MAX_NODES to prevent UI overload.
    """
    depth = min(depth, 3)

    try:
        records = await graph_store.query(
            cypher=(
                f"MATCH path = (center {{id: $id}})-[r*1..{depth}]-(neighbor) "
                "WITH center, neighbor, relationships(path) AS rels "
                "RETURN DISTINCT "
                "  neighbor.id AS id, "
                "  neighbor.title AS title, "
                "  neighbor.citation AS citation, "
                "  neighbor.court AS court, "
                "  neighbor.year AS year, "
                "  neighbor.cited_by_count AS cited_by_count, "
                "  [rel IN rels | {from: startNode(rel).id, to: endNode(rel).id, "
                "   type: type(rel), context: rel.context}] AS edges "
                "LIMIT $limit"
            ),
            params={"id": case_id, "limit": MAX_NODES},
        )
    except Exception as exc:
        logger.warning("Graph query failed for neighborhood: %s", exc, exc_info=True)
        return {"nodes": [], "edges": []}

    # Build deduplicated node and edge sets
    nodes_map: dict[str, dict] = {}
    edges_set: set[tuple[str, str, str]] = set()
    edges_list: list[dict] = []

    # Add center node
    try:
        center_node = await graph_store.get_node(case_id)
        if center_node:
            nodes_map[case_id] = {
                "id": case_id,
                "title": center_node.get("title"),
                "citation": center_node.get("citation"),
                "court": center_node.get("court"),
                "year": center_node.get("year"),
                "cited_by_count": center_node.get("cited_by_count", 0),
            }
    except Exception:
        nodes_map[case_id] = {"id": case_id}

    for record in records:
        nid = record.get("id")
        if nid and nid not in nodes_map:
            nodes_map[nid] = {
                "id": nid,
                "title": record.get("title"),
                "citation": record.get("citation"),
                "court": record.get("court"),
                "year": record.get("year"),
                "cited_by_count": record.get("cited_by_count", 0),
            }

        for edge in record.get("edges", []):
            edge_key = (edge["from"], edge["to"], edge["type"])
            if edge_key not in edges_set:
                edges_set.add(edge_key)
                edges_list.append({
                    "from": edge["from"],
                    "to": edge["to"],
                    "type": edge["type"],
                    "context": edge.get("context"),
                })

    return {
        "nodes": list(nodes_map.values()),
        "edges": edges_list,
    }


async def get_citation_chain(
    case_id: str,
    *,
    graph_store: GraphStore,
    max_depth: int = 3,
) -> dict:
    """Get the forward citation chain — cases this case cites, recursively."""
    max_depth = min(max_depth, 5)

    try:
        records = await graph_store.query(
            cypher=(
                f"MATCH path = (start {{id: $id}})-[:CITES*1..{max_depth}]->(cited) "
                "WITH cited, relationships(path) AS rels "
                "RETURN DISTINCT "
                "  cited.id AS id, "
                "  cited.title AS title, "
                "  cited.citation AS citation, "
                "  cited.court AS court, "
                "  cited.year AS year, "
                "  cited.cited_by_count AS cited_by_count, "
                "  [rel IN rels | {from: startNode(rel).id, to: endNode(rel).id, "
                "   type: type(rel)}] AS edges "
                "LIMIT $limit"
            ),
            params={"id": case_id, "limit": MAX_NODES},
        )
    except Exception as exc:
        logger.warning("Graph query failed for citation chain: %s", exc)
        return {"nodes": [], "edges": []}

    nodes_map: dict[str, dict] = {
        case_id: {"id": case_id}
    }
    edges_set: set[tuple[str, str]] = set()
    edges_list: list[dict] = []

    for record in records:
        nid = record.get("id")
        if nid and nid not in nodes_map:
            nodes_map[nid] = {
                "id": nid,
                "title": record.get("title"),
                "citation": record.get("citation"),
                "court": record.get("court"),
                "year": record.get("year"),
                "cited_by_count": record.get("cited_by_count", 0),
            }

        for edge in record.get("edges", []):
            edge_key = (edge["from"], edge["to"])
            if edge_key not in edges_set:
                edges_set.add(edge_key)
                edges_list.append({
                    "from": edge["from"],
                    "to": edge["to"],
                    "type": edge.get("type", "CITES"),
                })

    return {
        "nodes": list(nodes_map.values()),
        "edges": edges_list,
    }


async def get_authorities(
    case_id: str,
    *,
    graph_store: GraphStore,
    limit: int = 20,
) -> list[dict]:
    """Get the most-cited cases in the neighborhood of a given case.

    Finds cases within 2 hops and ranks by cited_by_count.
    """
    # Filter out cases marked as overruled in the graph (via is_overruled
    # property on Case nodes). Cases without the property are assumed valid.
    # TODO: Enrich Case nodes with is_overruled during ingestion based on
    # treatment detection so this filter becomes effective. Until then,
    # overruled cases may still appear in authority results.
    try:
        records = await graph_store.query(
            cypher=(
                "MATCH (center {id: $id})-[*1..2]-(neighbor) "
                "WHERE neighbor.id <> $id "
                "  AND COALESCE(neighbor.is_overruled, false) = false "
                "RETURN DISTINCT "
                "  neighbor.id AS id, "
                "  neighbor.title AS title, "
                "  neighbor.citation AS citation, "
                "  neighbor.court AS court, "
                "  neighbor.year AS year, "
                "  COALESCE(neighbor.cited_by_count, 0) AS cited_by_count, "
                "  COALESCE(neighbor.is_overruled, false) AS is_overruled "
                "ORDER BY cited_by_count DESC "
                "LIMIT $limit"
            ),
            params={"id": case_id, "limit": limit},
        )
    except Exception as exc:
        logger.warning("Graph query failed for authorities: %s", exc)
        return []

    return [
        {
            "id": r["id"],
            "title": r.get("title"),
            "citation": r.get("citation"),
            "court": r.get("court"),
            "year": r.get("year"),
            "cited_by_count": r.get("cited_by_count", 0),
            "is_overruled": r.get("is_overruled", False),
        }
        for r in records
    ]


async def get_graph_stats(
    *,
    graph_store: GraphStore,
    redis_client=None,
) -> dict:
    """Get global citation graph statistics."""
    cache_key = "graph:stats"

    # Check cache
    if redis_client is not None:
        try:
            import json

            cached = await redis_client.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception:
            pass

    try:
        count_result = await graph_store.query(
            cypher="MATCH (n:Case) RETURN count(n) AS total_judgments"
        )
        edge_result = await graph_store.query(
            cypher="MATCH ()-[r]->() RETURN count(r) AS total_edges"
        )
        top_result = await graph_store.query(
            cypher=(
                "MATCH (n:Case) "
                "WHERE n.cited_by_count IS NOT NULL "
                "RETURN n.id AS id, n.title AS title, n.citation AS citation, "
                "  n.cited_by_count AS cited_by_count "
                "ORDER BY n.cited_by_count DESC "
                "LIMIT 10"
            )
        )
    except Exception as exc:
        logger.warning("Graph stats query failed: %s", exc)
        return {"total_judgments": 0, "total_edges": 0, "most_cited": []}

    stats = {
        "total_judgments": count_result[0]["total_judgments"] if count_result else 0,
        "total_edges": edge_result[0]["total_edges"] if edge_result else 0,
        "most_cited": [
            {
                "id": r["id"],
                "title": r.get("title"),
                "citation": r.get("citation"),
                "cited_by_count": r.get("cited_by_count", 0),
            }
            for r in top_result
        ],
    }

    # Cache for 15 minutes
    if redis_client is not None:
        try:
            import json

            await redis_client.setex(cache_key, 900, json.dumps(stats))
        except Exception:
            pass

    return stats
