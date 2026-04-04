"""Citation graph traversal operations.

Provides functions for querying the Neo4j citation graph:
neighborhood exploration, citation chains, authority ranking, and statistics.
"""

from __future__ import annotations

import json
import logging

from app.core.interfaces import GraphStore

logger = logging.getLogger(__name__)

MAX_NODES = 200

_TREATMENT_TO_DISPLAY: dict[str | None, str] = {
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
                "  neighbor.pagerank_global AS pagerank_global, "
                "  neighbor.community_id AS community_id, "
                "  neighbor.community_label AS community_label, "
                "  neighbor.recent_citation_ratio AS recent_citation_ratio, "
                "  neighbor.treatment_positive_pct AS treatment_positive_pct, "
                "  neighbor.treatment_summary AS treatment_summary, "
                "  neighbor.bench_type AS bench_type, "
                "  neighbor.case_type AS case_type, "
                "  [rel IN rels | {from: startNode(rel).id, to: endNode(rel).id, "
                "   type: type(rel), treatment: rel.treatment, context: rel.context}] AS edges "
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

    # Add center node — return early if it doesn't exist in the graph
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
                "pagerank_global": center_node.get("pagerank_global"),
                "community_id": center_node.get("community_id"),
                "community_label": center_node.get("community_label"),
                "recent_citation_ratio": center_node.get("recent_citation_ratio"),
                "treatment_positive_pct": center_node.get("treatment_positive_pct"),
                "treatment_summary": center_node.get("treatment_summary"),
                "bench_type": center_node.get("bench_type"),
                "case_type": center_node.get("case_type"),
            }
        else:
            return {"nodes": [], "edges": [], "error": "Case not found in citation graph"}
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
                "pagerank_global": record.get("pagerank_global"),
                "community_id": record.get("community_id"),
                "community_label": record.get("community_label"),
                "recent_citation_ratio": record.get("recent_citation_ratio"),
                "treatment_positive_pct": record.get("treatment_positive_pct"),
                "treatment_summary": record.get("treatment_summary"),
                "bench_type": record.get("bench_type"),
                "case_type": record.get("case_type"),
            }

        for edge in record.get("edges", []):
            edge_key = (edge["from"], edge["to"], edge.get("type", "CITES"))
            if edge_key not in edges_set:
                edges_set.add(edge_key)
                treatment = edge.get("treatment")
                edges_list.append({
                    "from": edge["from"],
                    "to": edge["to"],
                    "type": _TREATMENT_TO_DISPLAY.get(treatment, "cites"),
                    "context": edge.get("context"),
                })

    # Filter edges to only include those whose endpoints are in nodes_map.
    # This prevents orphan edges when intermediate path nodes are missing
    # (e.g. depth > 1) or when Neo4j nodes lack an `id` property.
    valid_edges = [e for e in edges_list if e["from"] in nodes_map and e["to"] in nodes_map]

    return {
        "nodes": list(nodes_map.values()),
        "edges": valid_edges,
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
                "  cited.pagerank_global AS pagerank_global, "
                "  cited.community_id AS community_id, "
                "  cited.community_label AS community_label, "
                "  cited.recent_citation_ratio AS recent_citation_ratio, "
                "  cited.treatment_positive_pct AS treatment_positive_pct, "
                "  cited.treatment_summary AS treatment_summary, "
                "  cited.bench_type AS bench_type, "
                "  cited.case_type AS case_type, "
                "  [rel IN rels | {from: startNode(rel).id, to: endNode(rel).id, "
                "   type: type(rel), treatment: rel.treatment}] AS edges "
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
                "pagerank_global": record.get("pagerank_global"),
                "community_id": record.get("community_id"),
                "community_label": record.get("community_label"),
                "recent_citation_ratio": record.get("recent_citation_ratio"),
                "treatment_positive_pct": record.get("treatment_positive_pct"),
                "treatment_summary": record.get("treatment_summary"),
                "bench_type": record.get("bench_type"),
                "case_type": record.get("case_type"),
            }

        for edge in record.get("edges", []):
            edge_key = (edge["from"], edge["to"])
            if edge_key not in edges_set:
                edges_set.add(edge_key)
                treatment = edge.get("treatment")
                edges_list.append({
                    "from": edge["from"],
                    "to": edge["to"],
                    "type": _TREATMENT_TO_DISPLAY.get(treatment, "cites"),
                })

    valid_edges = [e for e in edges_list if e["from"] in nodes_map and e["to"] in nodes_map]

    return {
        "nodes": list(nodes_map.values()),
        "edges": valid_edges,
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
                "  COALESCE(neighbor.is_overruled, false) AS is_overruled, "
                "  neighbor.pagerank_global AS pagerank_global, "
                "  neighbor.community_id AS community_id, "
                "  neighbor.community_label AS community_label, "
                "  neighbor.recent_citation_ratio AS recent_citation_ratio, "
                "  neighbor.treatment_positive_pct AS treatment_positive_pct, "
                "  neighbor.treatment_summary AS treatment_summary, "
                "  neighbor.bench_type AS bench_type, "
                "  neighbor.case_type AS case_type "
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
            "pagerank_global": r.get("pagerank_global"),
            "community_id": r.get("community_id"),
            "community_label": r.get("community_label"),
            "recent_citation_ratio": r.get("recent_citation_ratio"),
            "treatment_positive_pct": r.get("treatment_positive_pct"),
            "treatment_summary": r.get("treatment_summary"),
            "bench_type": r.get("bench_type"),
            "case_type": r.get("case_type"),
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
            await redis_client.setex(cache_key, 900, json.dumps(stats))
        except Exception:
            pass

    return stats


async def get_dashboard(
    *,
    graph_store: GraphStore,
    redis_client=None,
    community_id: int | None = None,
    limit: int = 10,
) -> dict:
    """Get dashboard data: most cited, rising cases, recent negative treatments, communities."""
    cache_key = f"graph:dashboard:{community_id or 'all'}"

    # Check cache
    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception:
            pass

    community_filter = "WHERE n.community_id = $community_id" if community_id is not None else ""
    community_params: dict = {"limit": limit}
    if community_id is not None:
        community_params["community_id"] = community_id

    try:
        # 1. Most cited — ordered by pagerank_global
        most_cited_records = await graph_store.query(
            cypher=(
                f"MATCH (n:Case) {community_filter} "
                "WHERE n.pagerank_global IS NOT NULL "
                "RETURN n.id AS id, n.title AS title, n.citation AS citation, "
                "  n.court AS court, n.year AS year, "
                "  COALESCE(n.cited_by_count, 0) AS cited_by_count, "
                "  n.pagerank_global AS pagerank_global, "
                "  n.community_id AS community_id, "
                "  n.community_label AS community_label, "
                "  n.recent_citation_ratio AS recent_citation_ratio "
                "ORDER BY n.pagerank_global DESC "
                "LIMIT $limit"
            ),
            params=community_params,
        )

        # 2. Rising — recent_citation_ratio >= 0.4 AND cited_by_count >= 5
        rising_params: dict = {"limit": limit}
        rising_community_filter = ""
        if community_id is not None:
            rising_community_filter = "AND n.community_id = $community_id"
            rising_params["community_id"] = community_id

        rising_records = await graph_store.query(
            cypher=(
                "MATCH (n:Case) "
                "WHERE n.recent_citation_ratio >= 0.4 AND n.cited_by_count >= 5 "
                f"{rising_community_filter} "
                "RETURN n.id AS id, n.title AS title, n.citation AS citation, "
                "  n.court AS court, n.year AS year, "
                "  COALESCE(n.cited_by_count, 0) AS cited_by_count, "
                "  n.pagerank_global AS pagerank_global, "
                "  n.community_id AS community_id, "
                "  n.community_label AS community_label, "
                "  n.recent_citation_ratio AS recent_citation_ratio "
                "ORDER BY n.recent_citation_ratio DESC, n.cited_by_count DESC "
                "LIMIT $limit"
            ),
            params=rising_params,
        )

        # 3. Recently negative — negative treatments ordered by citing year
        neg_params: dict = {"limit": limit}
        neg_community_filter = ""
        if community_id is not None:
            neg_community_filter = "AND cited.community_id = $community_id"
            neg_params["community_id"] = community_id

        neg_records = await graph_store.query(
            cypher=(
                "MATCH (citing:Case)-[r:CITES]->(cited:Case) "
                "WHERE r.treatment IN ['overruled','not_followed','per_incuriam','distinguished'] "
                f"{neg_community_filter} "
                "RETURN cited.id AS id, cited.title AS title, cited.citation AS citation, "
                "  cited.court AS court, cited.year AS year, "
                "  COALESCE(cited.cited_by_count, 0) AS cited_by_count, "
                "  cited.pagerank_global AS pagerank_global, "
                "  cited.community_id AS community_id, "
                "  cited.community_label AS community_label, "
                "  r.treatment AS negative_treatment, "
                "  citing.title AS by_case_title, "
                "  citing.year AS by_case_year "
                "ORDER BY citing.year DESC "
                "LIMIT $limit"
            ),
            params=neg_params,
        )

        # 4. Communities — group by community_id
        community_records = await graph_store.query(
            cypher=(
                "MATCH (n:Case) "
                "WHERE n.community_id IS NOT NULL "
                "RETURN n.community_id AS community_id, "
                "  n.community_label AS community_label, "
                "  count(n) AS count "
                "ORDER BY count DESC"
            ),
        )
    except Exception as exc:
        logger.warning("Graph dashboard query failed: %s", exc, exc_info=True)
        return {"most_cited": [], "rising": [], "recently_negative": [], "communities": []}

    def _node_dict(r: dict) -> dict:
        return {
            "id": r["id"],
            "title": r.get("title"),
            "citation": r.get("citation"),
            "court": r.get("court"),
            "year": r.get("year"),
            "cited_by_count": r.get("cited_by_count", 0),
            "pagerank_global": r.get("pagerank_global"),
            "community_id": r.get("community_id"),
            "community_label": r.get("community_label"),
            "recent_citation_ratio": r.get("recent_citation_ratio"),
        }

    result = {
        "most_cited": [_node_dict(r) for r in most_cited_records],
        "rising": [_node_dict(r) for r in rising_records],
        "recently_negative": [
            {
                "case": _node_dict(r),
                "negative_treatment": r.get("negative_treatment"),
                "by_case_title": r.get("by_case_title"),
                "by_case_year": r.get("by_case_year"),
            }
            for r in neg_records
        ],
        "communities": [
            {
                "community_id": r.get("community_id"),
                "community_label": r.get("community_label"),
                "count": r.get("count", 0),
            }
            for r in community_records
        ],
    }

    # Cache for 1 hour
    if redis_client is not None:
        try:
            await redis_client.setex(cache_key, 3600, json.dumps(result))
        except Exception:
            pass

    return result


async def get_shortest_path(
    from_id: str,
    to_id: str,
    *,
    graph_store: GraphStore,
    max_depth: int = 6,
) -> dict:
    """Find shortest citation path between two cases."""
    max_depth = min(max_depth, 10)

    # Verify both nodes exist
    from_node = await graph_store.get_node(from_id)
    to_node = await graph_store.get_node(to_id)

    if from_node is None:
        return {"error": f"Case not found: {from_id}", "paths": []}
    if to_node is None:
        return {"error": f"Case not found: {to_id}", "paths": []}

    def _format_node(n: dict) -> dict:
        return {
            "id": n.get("id"),
            "title": n.get("title"),
            "citation": n.get("citation"),
            "court": n.get("court"),
            "year": n.get("year"),
            "cited_by_count": n.get("cited_by_count", 0),
            "pagerank_global": n.get("pagerank_global"),
            "community_id": n.get("community_id"),
            "community_label": n.get("community_label"),
            "recent_citation_ratio": n.get("recent_citation_ratio"),
            "treatment_positive_pct": n.get("treatment_positive_pct"),
            "treatment_summary": n.get("treatment_summary"),
            "bench_type": n.get("bench_type"),
            "case_type": n.get("case_type"),
        }

    from_case = _format_node(from_node)
    to_case = _format_node(to_node)

    paths: list[dict] = []

    try:
        # Try forward direction: from -> to
        forward_records = await graph_store.query(
            cypher=(
                f"MATCH path = shortestPath((a:Case {{id: $from_id}})-[:CITES*1..{max_depth}]->(b:Case {{id: $to_id}})) "
                "RETURN [n IN nodes(path) | n.id] AS node_ids, "
                "  [r IN relationships(path) | {from: startNode(r).id, to: endNode(r).id, "
                "   treatment: r.treatment, context: r.context}] AS edges"
            ),
            params={"from_id": from_id, "to_id": to_id},
        )

        # Try reverse direction: to -> from
        reverse_records = await graph_store.query(
            cypher=(
                f"MATCH path = shortestPath((a:Case {{id: $to_id}})-[:CITES*1..{max_depth}]->(b:Case {{id: $from_id}})) "
                "RETURN [n IN nodes(path) | n.id] AS node_ids, "
                "  [r IN relationships(path) | {from: startNode(r).id, to: endNode(r).id, "
                "   treatment: r.treatment, context: r.context}] AS edges"
            ),
            params={"from_id": from_id, "to_id": to_id},
        )

        all_records = list(forward_records) + list(reverse_records)

        for record in all_records:
            node_ids = record.get("node_ids", [])
            # Fetch full node data for each node in the path
            path_nodes = []
            for nid in node_ids:
                if nid == from_id:
                    path_nodes.append(from_case)
                elif nid == to_id:
                    path_nodes.append(to_case)
                else:
                    node_data = await graph_store.get_node(nid)
                    if node_data:
                        path_nodes.append(_format_node(node_data))
                    else:
                        path_nodes.append({"id": nid})

            path_edges = [
                {
                    "from": e["from"],
                    "to": e["to"],
                    "type": _TREATMENT_TO_DISPLAY.get(e.get("treatment"), "cites"),
                    "context": e.get("context"),
                }
                for e in record.get("edges", [])
            ]

            paths.append({"nodes": path_nodes, "edges": path_edges})
    except Exception as exc:
        logger.warning("Graph shortest path query failed: %s", exc, exc_info=True)

    return {
        "paths": paths,
        "from_case": from_case,
        "to_case": to_case,
    }


async def get_treatment_summary(
    case_id: str,
    *,
    graph_store: GraphStore,
    redis_client=None,
) -> dict:
    """Get a treatment summary for a case — how other cases have treated it."""
    cache_key = f"graph:treatment:{case_id}"

    # Check cache
    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception:
            pass

    node = await graph_store.get_node(case_id)
    if node is None:
        return {"error": f"Case not found: {case_id}"}

    try:
        records = await graph_store.query(
            cypher=(
                "MATCH (citing:Case)-[r:CITES]->(cited:Case {id: $case_id}) "
                "RETURN citing.id AS id, citing.title AS title, citing.year AS year, "
                "  citing.citation AS citation, r.context AS context, "
                "  r.treatment AS treatment "
                "ORDER BY citing.year DESC"
            ),
            params={"case_id": case_id},
        )
    except Exception as exc:
        logger.warning("Graph treatment summary query failed: %s", exc, exc_info=True)
        return {
            "case_id": case_id,
            "treatment_positive_pct": 0.0,
            "verdict": "Unknown",
            "total_citations": 0,
            "breakdown": {},
        }

    # Aggregate into breakdown
    breakdown: dict[str, list[dict]] = {}
    for r in records:
        treatment = r.get("treatment") or "referred_to"
        if treatment not in breakdown:
            breakdown[treatment] = []
        breakdown[treatment].append({
            "id": r["id"],
            "title": r.get("title"),
            "year": r.get("year"),
            "citation": r.get("citation"),
            "context": r.get("context"),
        })

    total = len(records)
    positive_treatments = {"affirmed", "followed", "referred_to", "explained"}
    negative_treatments = {"overruled", "not_followed", "per_incuriam"}

    positive_count = sum(
        len(breakdown.get(t, [])) for t in positive_treatments
    )
    positive_pct = positive_count / total if total > 0 else 0.0

    # Compute verdict
    has_severe_negative = any(t in breakdown for t in ("overruled", "per_incuriam"))
    if has_severe_negative:
        verdict = "Overruled"
    elif positive_pct < 0.5:
        verdict = "Cautionary"
    elif positive_pct >= 0.8:
        verdict = "Followed"
    else:
        verdict = "Mixed"

    result = {
        "case_id": case_id,
        "treatment_positive_pct": round(positive_pct, 3),
        "verdict": verdict,
        "total_citations": total,
        "breakdown": breakdown,
    }

    # Cache for 15 minutes
    if redis_client is not None:
        try:
            await redis_client.setex(cache_key, 900, json.dumps(result))
        except Exception:
            pass

    return result
