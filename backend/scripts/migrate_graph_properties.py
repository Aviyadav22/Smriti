"""One-time migration: backfill cited_by_count and is_overruled on Neo4j Case nodes.

Also resolves placeholder nodes that match already-ingested cases.
Idempotent — safe to run multiple times.

Usage:
    cd backend
    python -m scripts.migrate_graph_properties [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def migrate(dry_run: bool = False) -> None:
    # Late imports so --help works without full app setup
    from app.core.config import settings
    from app.core.providers.graph.neo4j_store import Neo4jGraph

    graph = Neo4jGraph()  # reads settings (NEO4J_URI, etc.) from env
    try:
        logger.info("Connected to Neo4j at %s", settings.neo4j_uri)

        # ---- Step 1: Backfill cited_by_count ----
        logger.info("Step 1: Backfilling cited_by_count...")
        if not dry_run:
            result = await graph.query(
                "MATCH (c:Case) "
                "SET c.cited_by_count = count { (c)<-[:CITES]-() } "
                "RETURN count(c) AS updated"
            )
            count = result[0]["updated"] if result else 0
            logger.info("  Updated cited_by_count on %d nodes", count)
        else:
            result = await graph.query("MATCH (c:Case) RETURN count(c) AS total")
            logger.info("  [DRY RUN] Would update %d nodes", result[0]["total"] if result else 0)

        # ---- Step 2: Set is_overruled from existing treatment data ----
        logger.info("Step 2: Setting is_overruled flags...")
        if not dry_run:
            result = await graph.query(
                "MATCH (target:Case)<-[r:CITES]-(source) "
                "WHERE r.treatment = 'overruled' "
                "SET target.is_overruled = true "
                "RETURN count(DISTINCT target) AS flagged"
            )
            count = result[0]["flagged"] if result else 0
            logger.info("  Flagged %d cases as overruled", count)
        else:
            result = await graph.query(
                "MATCH (target:Case)<-[r:CITES]-(source) "
                "WHERE r.treatment = 'overruled' "
                "RETURN count(DISTINCT target) AS flagged"
            )
            logger.info("  [DRY RUN] Would flag %d cases", result[0]["flagged"] if result else 0)

        # ---- Step 3: Resolve placeholders matching real cases ----
        logger.info("Step 3: Resolving placeholder nodes...")
        # First count how many are resolvable
        count_result = await graph.query(
            "MATCH (real:Case), (placeholder:Case) "
            "WHERE NOT real.id STARTS WITH 'ref_' "
            "  AND placeholder.id STARTS WITH 'ref_' "
            "  AND placeholder.citation = real.citation "
            "  AND real.id <> placeholder.id "
            "RETURN count(placeholder) AS resolvable"
        )
        resolvable = count_result[0]["resolvable"] if count_result else 0

        if resolvable == 0:
            logger.info("  No resolvable placeholders found")
        elif dry_run:
            logger.info("  [DRY RUN] Would resolve %d placeholder nodes", resolvable)
        else:
            # Transfer incoming edges from placeholder to real node
            await graph.query(
                "MATCH (real:Case), (placeholder:Case) "
                "WHERE NOT real.id STARTS WITH 'ref_' "
                "  AND placeholder.id STARTS WITH 'ref_' "
                "  AND placeholder.citation = real.citation "
                "  AND real.id <> placeholder.id "
                "WITH real, placeholder "
                "MATCH (src)-[r:CITES]->(placeholder) "
                "WHERE src <> real "
                "CREATE (src)-[r2:CITES]->(real) SET r2 = properties(r) "
                "DELETE r"
            )
            # Transfer outgoing edges from placeholder to real node
            await graph.query(
                "MATCH (real:Case), (placeholder:Case) "
                "WHERE NOT real.id STARTS WITH 'ref_' "
                "  AND placeholder.id STARTS WITH 'ref_' "
                "  AND placeholder.citation = real.citation "
                "  AND real.id <> placeholder.id "
                "WITH real, placeholder "
                "MATCH (placeholder)-[r:CITES]->(tgt) "
                "WHERE tgt <> real "
                "CREATE (real)-[r2:CITES]->(tgt) SET r2 = properties(r) "
                "DELETE r"
            )
            # Delete placeholder nodes (now edge-less)
            result = await graph.query(
                "MATCH (placeholder:Case) "
                "WHERE placeholder.id STARTS WITH 'ref_' "
                "  AND NOT (placeholder)-[]-() "
                "DETACH DELETE placeholder "
                "RETURN count(placeholder) AS deleted"
            )
            deleted = result[0]["deleted"] if result else 0
            logger.info("  Resolved %d placeholder nodes (%d fully deleted)", resolvable, deleted)

        # ---- Step 4: Summary stats ----
        logger.info("Step 4: Summary...")
        stats = await graph.query(
            "MATCH (c:Case) "
            "RETURN count(c) AS total_nodes, "
            "       count(CASE WHEN c.id STARTS WITH 'ref_' THEN 1 END) AS placeholders, "
            "       count(CASE WHEN c.is_overruled = true THEN 1 END) AS overruled, "
            "       count(CASE WHEN c.cited_by_count > 0 THEN 1 END) AS has_citations"
        )
        if stats:
            s = stats[0]
            logger.info(
                "  Total nodes: %d | Placeholders remaining: %d | Overruled: %d | With citations: %d",
                s["total_nodes"],
                s["placeholders"],
                s["overruled"],
                s["has_citations"],
            )

        logger.info("Migration complete!")

    finally:
        await graph.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill graph node properties (cited_by_count, is_overruled, placeholder resolution)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()
    asyncio.run(migrate(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
