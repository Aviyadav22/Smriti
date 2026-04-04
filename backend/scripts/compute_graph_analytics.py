"""Compute graph analytics and write results back to Neo4j.

Runs Louvain community detection, PageRank, rising authority scoring,
and treatment aggregation on the citation graph. Results are stored as
node properties for fast API retrieval.

Also enriches Neo4j Case nodes with metadata from PostgreSQL (jurisdiction,
coram_size, issue_tags, etc.) and creates IssueTopic / StatuteSection nodes.

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
from app.core.legal.taxonomy import get_category_for_tag, normalize_issue_tags

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


# Mapping from raw keywords/act abbreviations to clean practice area labels.
# Order matters: first match wins.  Each entry is (set of trigger terms, label).
_PRACTICE_AREA_TRIGGERS: list[tuple[set[str], str]] = [
    # Criminal
    ({"ipc", "crpc", "indian penal code", "code of criminal procedure", "murder",
      "criminal appeal", "bail", "fir", "chargesheet", "dowry", "pocso",
      "narcotic", "ndps", "life imprisonment", "death sentence", "criminal conspiracy"}, "Criminal Law"),
    # Constitutional
    ({"coi", "constitution of india", "article 14", "article 19", "article 21",
      "article 32", "article 226", "fundamental rights", "writ petition",
      "constitutional", "pil", "public interest"}, "Constitutional Law"),
    # Arbitration
    ({"arbitration", "aca", "arbitration and conciliation act", "arbitral tribunal",
      "arbitral award", "section 34", "section 11"}, "Arbitration"),
    # Land & Property
    ({"land acquisition", "laa", "larr", "right to fair compensation",
      "land acquisition act", "tpa", "transfer of property", "property",
      "specific relief", "specific performance", "easement"}, "Land & Property"),
    # Tax
    ({"income tax", "ita", "gst", "customs", "excise", "central excise",
      "service tax", "tax", "taxation", "vat", "sales tax", "stamp duty"}, "Tax Law"),
    # Labour & Service
    ({"service law", "service", "industrial disputes", "ida",
      "labour", "esic", "epf", "workmen", "dismissal", "termination",
      "compassionate appointment", "selection process", "promotion"}, "Labour & Service"),
    # Insolvency
    ({"ibc", "insolvency", "insolvency and bankruptcy code", "nclt", "nclat",
      "corporate insolvency", "liquidation", "moratorium", "resolution plan"}, "Insolvency"),
    # Family
    ({"hindu marriage act", "divorce", "maintenance", "custody", "matrimonial",
      "domestic violence", "guardianship", "adoption", "family"}, "Family Law"),
    # Civil Procedure
    ({"cpc", "code of civil procedure", "civil appeal", "section 100 cpc",
      "order 7 rule 11", "res judicata", "limitation", "limitation act",
      "suit", "decree", "execution"}, "Civil Procedure"),
    # Contract & Commercial
    ({"contract", "indian contract act", "specific relief", "negotiable instruments",
      "nia", "cheque dishonour", "section 138", "commercial"}, "Contract & Commercial"),
    # Environmental
    ({"environment", "ngt", "pollution", "forest", "wildlife",
      "environmental protection", "mining"}, "Environmental Law"),
    # Electricity & Regulatory
    ({"electricity", "electricity act", "tariff", "regulatory",
      "telecom", "trai", "competition act", "cci"}, "Regulatory Law"),
    # Motor Vehicles / Tort
    ({"motor vehicles", "mva", "compensation", "motor accident",
      "accident", "negligence", "tort"}, "Motor Accident & Tort"),
    # Company Law
    ({"companies act", "company law", "winding up", "oppression",
      "mismanagement", "shareholder", "director"}, "Company Law"),
    # Evidence
    ({"iea", "indian evidence act", "evidence", "witness",
      "dying declaration", "expert opinion"}, "Evidence"),
]


def _label_community(G: nx.DiGraph, member_ids: list[str]) -> str:
    """Map a community to a clean legal practice area label."""
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

    # Collect all keywords (lowered) for matching
    all_keywords_lower = {kw.lower() for kw in keyword_counter}

    # Find best matching practice area
    best_label = None
    best_overlap = 0
    for triggers, label in _PRACTICE_AREA_TRIGGERS:
        overlap = len(triggers & all_keywords_lower)
        if overlap > best_overlap:
            best_overlap = overlap
            best_label = label

    if best_label:
        return best_label

    # Fallback: use top 2 keywords cleaned up
    top = [kw for kw, _ in keyword_counter.most_common(2)]
    return ", ".join(top) if top else "Other"


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
# 8. PostgreSQL enrichment
# ---------------------------------------------------------------------------


async def fetch_pg_metadata(db_session: object) -> list[dict]:
    """Query PostgreSQL for case metadata to enrich Neo4j nodes.

    Args:
        db_session: An async SQLAlchemy session.

    Returns:
        List of dicts with case metadata fields.
    """
    from sqlalchemy import text

    result = await db_session.execute(text(  # type: ignore[union-attr]
        """
        SELECT id::text, jurisdiction, coram_size, is_reportable, opinion_type,
               issue_classification, primary_legal_issue, fact_pattern_summary,
               headnotes
        FROM cases WHERE id IS NOT NULL
        """
    ))
    rows = result.mappings().all()  # type: ignore[union-attr]
    return [dict(r) for r in rows]


async def fetch_statute_interpretations(db_session: object) -> list[dict]:
    """Query PostgreSQL for statute section interpretations.

    Args:
        db_session: An async SQLAlchemy session.

    Returns:
        List of dicts with case_id, section, act, interpretation_summary.
    """
    from sqlalchemy import text

    result = await db_session.execute(text(  # type: ignore[union-attr]
        """
        SELECT c.id::text AS case_id,
               si.value->>'section' AS section,
               si.value->>'act' AS act,
               si.value->>'interpretation_summary' AS interpretation_summary
        FROM cases c,
             jsonb_array_elements(c.statute_sections_interpreted) AS si(value)
        WHERE c.statute_sections_interpreted IS NOT NULL
          AND c.statute_sections_interpreted::text != '[]'
        """
    ))
    rows = result.mappings().all()  # type: ignore[union-attr]
    return [dict(r) for r in rows]


def _extract_headnote_text(headnotes: object) -> str:
    """Extract the first headnote proposition text, max 500 chars.

    Headnotes may be a JSON string or already-parsed list/dict.
    """
    if headnotes is None:
        return ""

    parsed = headnotes
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except (json.JSONDecodeError, ValueError):
            return parsed[:500]

    if isinstance(parsed, list) and len(parsed) > 0:
        first = parsed[0]
        if isinstance(first, dict):
            text = first.get("proposition") or first.get("text") or first.get("headnote") or ""
            return str(text)[:500]
        if isinstance(first, str):
            return first[:500]

    if isinstance(parsed, dict):
        text = parsed.get("proposition") or parsed.get("text") or parsed.get("headnote") or ""
        return str(text)[:500]

    return ""


async def enrich_neo4j_from_postgres(
    graph_store: GraphStore,
    pg_rows: list[dict],
) -> int:
    """Write PostgreSQL metadata to Neo4j Case nodes via UNWIND batches.

    Returns:
        Number of nodes updated.
    """
    if not pg_rows:
        return 0

    rows: list[dict] = []
    for r in pg_rows:
        tags = normalize_issue_tags(r.get("issue_classification") or [])
        issue_tags = ",".join(tags) if tags else ""

        primary = r.get("primary_legal_issue") or ""
        fact_summary = r.get("fact_pattern_summary") or ""

        rows.append({
            "id": r["id"],
            "jurisdiction": r.get("jurisdiction") or "",
            "coram_size": int(r.get("coram_size") or 0),
            "is_reportable": bool(r.get("is_reportable")),
            "opinion_type": r.get("opinion_type") or "",
            "issue_tags": issue_tags,
            "primary_legal_issue": str(primary)[:200],
            "fact_pattern_summary": str(fact_summary)[:500],
            "headnote_text": _extract_headnote_text(r.get("headnotes")),
        })

    total = 0
    for i in range(0, len(rows), WRITE_BATCH_SIZE):
        batch = rows[i : i + WRITE_BATCH_SIZE]
        await graph_store.query(
            """
            UNWIND $rows AS row
            MATCH (c:Case {id: row.id})
            SET c.jurisdiction = row.jurisdiction,
                c.coram_size = row.coram_size,
                c.is_reportable = row.is_reportable,
                c.opinion_type = row.opinion_type,
                c.issue_tags = row.issue_tags,
                c.primary_legal_issue = row.primary_legal_issue,
                c.fact_pattern_summary = row.fact_pattern_summary,
                c.headnote_text = row.headnote_text
            """,
            params={"rows": batch},
        )
        total += len(batch)

    return total


async def create_issue_topic_nodes(
    graph_store: GraphStore,
    pg_rows: list[dict],
) -> int:
    """Create IssueTopic nodes and CLASSIFIED_AS edges from case issue tags.

    Returns:
        Number of edges created/merged.
    """
    if not pg_rows:
        return 0

    rows: list[dict] = []
    for r in pg_rows:
        tags = normalize_issue_tags(r.get("issue_classification") or [])
        for tag in tags:
            category = get_category_for_tag(tag) or "Other"
            subtopic = tag.split(".", 1)[1] if "." in tag else tag
            rows.append({
                "case_id": r["id"],
                "tag": tag,
                "category": category,
                "subtopic": subtopic,
            })

    if not rows:
        return 0

    total = 0
    for i in range(0, len(rows), WRITE_BATCH_SIZE):
        batch = rows[i : i + WRITE_BATCH_SIZE]
        await graph_store.query(
            """
            UNWIND $rows AS row
            MERGE (t:IssueTopic {id: row.tag})
            ON CREATE SET t.category = row.category, t.subtopic = row.subtopic
            WITH t, row
            MATCH (c:Case {id: row.case_id})
            MERGE (c)-[:CLASSIFIED_AS]->(t)
            """,
            params={"rows": batch},
        )
        total += len(batch)

    return total


async def create_statute_section_nodes(
    graph_store: GraphStore,
    statute_rows: list[dict],
) -> int:
    """Create StatuteSection nodes and INTERPRETS edges from statute data.

    Returns:
        Number of edges created/merged.
    """
    if not statute_rows:
        return 0

    rows: list[dict] = []
    for r in statute_rows:
        section = r.get("section") or ""
        act = r.get("act") or ""
        if not section and not act:
            continue

        section_id = f"{act}_{section}".lower().replace(" ", "_").replace(",", "")[:100]
        interpretation = r.get("interpretation_summary") or ""

        rows.append({
            "case_id": r["case_id"],
            "section_id": section_id,
            "section": section,
            "act": act,
            "interpretation": str(interpretation)[:500],
        })

    if not rows:
        return 0

    total = 0
    for i in range(0, len(rows), WRITE_BATCH_SIZE):
        batch = rows[i : i + WRITE_BATCH_SIZE]
        await graph_store.query(
            """
            UNWIND $rows AS row
            MERGE (s:StatuteSection {id: row.section_id})
            ON CREATE SET s.section = row.section, s.act = row.act
            WITH s, row
            MATCH (c:Case {id: row.case_id})
            MERGE (c)-[r:INTERPRETS]->(s)
            SET r.interpretation = row.interpretation
            """,
            params={"rows": batch},
        )
        total += len(batch)

    return total


# ---------------------------------------------------------------------------
# 9. Cache invalidation (renumbered from 8)
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
# 10. Main orchestrator
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

    # --- Enrichment from PostgreSQL ---
    logger.info("Enriching Neo4j from PostgreSQL metadata...")
    from app.db.postgres import async_session_factory

    async with async_session_factory() as db_session:
        pg_rows = await fetch_pg_metadata(db_session)
        logger.info("Fetched %d cases from PostgreSQL", len(pg_rows))

        enriched = await enrich_neo4j_from_postgres(graph_store, pg_rows)
        logger.info("Enriched %d Neo4j nodes with PG metadata", enriched)

        issue_count = await create_issue_topic_nodes(graph_store, pg_rows)
        logger.info("Created/updated %d IssueTopic edges", issue_count)

        statute_rows = await fetch_statute_interpretations(db_session)
        statute_count = await create_statute_section_nodes(graph_store, statute_rows)
        logger.info("Created/updated %d StatuteSection edges", statute_count)

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
        from app.core.dependencies import get_graph_store
        from app.db.redis_client import get_redis

        graph_store = get_graph_store()
        redis_client = None
        try:
            redis_client = await get_redis()
        except Exception:
            logger.warning("Redis not available — skipping cache invalidation")

        try:
            await run_analytics(graph_store, redis_client)
        finally:
            if redis_client is not None:
                await redis_client.aclose()

    asyncio.run(main())
