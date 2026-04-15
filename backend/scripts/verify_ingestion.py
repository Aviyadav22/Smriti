"""Post-ingestion verification: checks PostgreSQL, Pinecone, and Neo4j consistency.

Usage:
    python scripts/verify_ingestion.py
    python scripts/verify_ingestion.py --sample 50
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.dependencies import get_graph_store, get_vector_store
from app.db.postgres import async_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("verify_ingestion")


async def verify(sample_size: int = 100) -> dict:
    """Run cross-store consistency checks."""
    results = {"pg_total": 0, "vector_mismatches": [], "graph_missing": [], "fts_issues": []}

    async with async_session_factory() as db:
        # 1. Count total cases in PostgreSQL
        row = await db.execute(text("SELECT COUNT(*) FROM cases"))
        results["pg_total"] = row.scalar() or 0
        logger.info("PostgreSQL: %d cases", results["pg_total"])

        # 2. Get sample of case IDs with chunk counts
        sample_rows = await db.execute(
            text("SELECT id, citation, chunk_count FROM cases ORDER BY RANDOM() LIMIT :limit"),
            {"limit": sample_size},
        )
        samples = sample_rows.fetchall()
        logger.info("Sampling %d cases for verification", len(samples))

        # 3. Check vector store for each sample
        vector_store = get_vector_store()
        mismatches = 0
        for case_id, citation, expected_chunks in samples:
            case_id_str = str(case_id)
            try:
                # Query Pinecone for vectors with this case_id.
                # Use top_k matching expected chunks to detect partial failures
                # (top_k=1 can't distinguish "1 of 20" from "all present").
                check_k = min(expected_chunks or 1, 10000)
                query_result = await vector_store.query(
                    vector=[0.0] * 1536,  # dummy
                    top_k=check_k,
                    filter={"case_id": case_id_str},
                    include_metadata=False,
                )
                actual_count = len(query_result.get("matches", []))
                if expected_chunks and expected_chunks > 0 and actual_count < expected_chunks:
                    results["vector_mismatches"].append({
                        "case_id": case_id_str,
                        "citation": citation,
                        "expected": expected_chunks,
                        "found": actual_count,
                    })
                    mismatches += 1
            except Exception as exc:
                logger.warning("Vector check failed for %s: %s", case_id_str, exc)

        logger.info("Vector mismatches: %d / %d samples", mismatches, len(samples))

        # 4. Check Neo4j node count
        try:
            graph_store = get_graph_store()
            graph_result = await graph_store.query("MATCH (c:Case) RETURN count(c) AS cnt")
            graph_count = graph_result[0]["cnt"] if graph_result else 0
            results["graph_count"] = graph_count
            logger.info("Neo4j: %d Case nodes (PG: %d)", graph_count, results["pg_total"])
        except Exception as exc:
            logger.warning("Neo4j check failed: %s", exc)
            results["graph_count"] = -1

        # 5. FTS spot check
        test_queries = ["murder Section 302", "Article 21 fundamental rights", "arbitration"]
        for q in test_queries:
            try:
                fts_result = await db.execute(
                    text(
                        "SELECT COUNT(*) FROM cases "
                        "WHERE searchable_text @@ websearch_to_tsquery('english', :q)"
                    ),
                    {"q": q},
                )
                count = fts_result.scalar() or 0
                logger.info("FTS '%s': %d results", q, count)
                if count == 0:
                    results["fts_issues"].append(q)
            except Exception as exc:
                logger.warning("FTS check '%s' failed: %s", q, exc)

    # Summary
    logger.info("=== VERIFICATION SUMMARY ===")
    logger.info("PostgreSQL cases: %d", results["pg_total"])
    logger.info("Vector mismatches: %d", len(results["vector_mismatches"]))
    logger.info("Graph count: %s", results.get("graph_count", "N/A"))
    logger.info("FTS issues: %s", results["fts_issues"] or "None")

    if results["vector_mismatches"]:
        logger.warning("Cases with missing vectors:")
        for m in results["vector_mismatches"][:10]:
            logger.warning("  %s (%s): expected %d chunks", m["case_id"], m["citation"], m["expected"])

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify ingestion consistency across stores")
    parser.add_argument("--sample", type=int, default=100, help="Number of cases to sample")
    args = parser.parse_args()
    asyncio.run(verify(sample_size=args.sample))


if __name__ == "__main__":
    main()
