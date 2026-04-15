#!/usr/bin/env python3
"""Purge bad/incomplete cases from ALL stores (PG, Pinecone, Neo4j).

Keeps only the 1,991 verified cases. Deletes everything else from:
- PostgreSQL (cases table + related data)
- Pinecone (vectors for deleted case IDs)
- Neo4j (case nodes for deleted case IDs + all stale orphan nodes)

Usage:
    python scripts/purge_bad_cases.py --dry-run   # preview only
    python scripts/purge_bad_cases.py              # execute purge
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("purge")


async def purge(dry_run: bool) -> None:
    # ── Load delete list ─────────────────────────────────────────────
    delete_path = Path("trial_reports/delete_ids.json")
    keep_path = Path("trial_reports/keep_ids.json")
    if not delete_path.exists() or not keep_path.exists():
        logger.error("Run the identification step first — delete_ids.json / keep_ids.json not found")
        return

    delete_ids: list[str] = json.loads(delete_path.read_text(encoding="utf-8"))
    keep_ids: list[str] = json.loads(keep_path.read_text(encoding="utf-8"))
    logger.info("KEEP: %d cases, DELETE: %d cases", len(keep_ids), len(delete_ids))

    if dry_run:
        logger.info("[DRY RUN] Would delete %d cases from PG, Pinecone, Neo4j", len(delete_ids))
        return

    # ══════════════════════════════════════════════════════════════════
    # STEP 1: PostgreSQL — delete cases NOT in keep list
    # ══════════════════════════════════════════════════════════════════
    logger.info("=" * 60)
    logger.info("STEP 1: PostgreSQL — deleting %d cases", len(delete_ids))
    logger.info("=" * 60)

    import asyncpg

    from app.core.config import settings
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)

    # Verify counts before deletion
    total_before = await conn.fetchval("SELECT count(*) FROM cases")
    keep_count = await conn.fetchval(
        "SELECT count(*) FROM cases WHERE id = ANY($1::uuid[])",
        keep_ids,
    )
    delete_count = await conn.fetchval(
        "SELECT count(*) FROM cases WHERE id = ANY($1::uuid[])",
        delete_ids,
    )
    logger.info("PG before: total=%d, keep=%d, delete=%d", total_before, keep_count, delete_count)

    if keep_count != len(keep_ids):
        logger.error("ABORT: keep count mismatch (%d vs %d)", keep_count, len(keep_ids))
        await conn.close()
        return

    # Delete dependent rows first (FK constraints)
    dependent_tables = [
        "graph_build_queue",
        "case_citation_equivalents",
        "case_sections",
        "case_statute_interpretations",
        "case_vectors",
        "audio_digests",
        "documents",
    ]
    for table in dependent_tables:
        result = await conn.execute(
            f"DELETE FROM {table} WHERE case_id = ANY($1::uuid[])",
            delete_ids,
        )
        count = int(result.split()[-1])
        if count > 0:
            logger.info("  Cleaned %s: %d rows deleted", table, count)

    # Also clean citations table (has source_case_id and target_case_id)
    result = await conn.execute(
        "DELETE FROM citations WHERE source_case_id = ANY($1::uuid[]) OR target_case_id = ANY($1::uuid[])",
        delete_ids,
    )
    count = int(result.split()[-1])
    if count > 0:
        logger.info("  Cleaned citations: %d rows deleted", count)

    # Now delete cases in batches
    batch_size = 500
    deleted_pg = 0
    for i in range(0, len(delete_ids), batch_size):
        batch = delete_ids[i:i + batch_size]
        result = await conn.execute(
            "DELETE FROM cases WHERE id = ANY($1::uuid[])",
            batch,
        )
        count = int(result.split()[-1])
        deleted_pg += count
        logger.info("  PG batch %d: deleted %d (total: %d/%d)",
                     i // batch_size + 1, count, deleted_pg, len(delete_ids))

    total_after = await conn.fetchval("SELECT count(*) FROM cases")
    logger.info("PG after: %d cases (deleted %d)", total_after, deleted_pg)
    assert total_after == len(keep_ids), f"PG count {total_after} != keep {len(keep_ids)}"
    await conn.close()

    # ══════════════════════════════════════════════════════════════════
    # STEP 2: Pinecone — delete vectors for deleted case IDs
    # ══════════════════════════════════════════════════════════════════
    logger.info("=" * 60)
    logger.info("STEP 2: Pinecone — deleting vectors for %d cases", len(delete_ids))
    logger.info("=" * 60)

    from pinecone import Pinecone
    pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
    idx = pc.Index(host=os.environ.get("PINECONE_HOST"))

    stats_before = idx.describe_index_stats()
    logger.info("Pinecone before: %d vectors", stats_before.total_vector_count)

    # Delete by metadata filter — batch by case_id
    # Pinecone delete-by-filter: delete all vectors where case_id matches
    pine_deleted = 0
    for i in range(0, len(delete_ids), 100):
        batch = delete_ids[i:i + 100]
        for cid in batch:
            try:
                idx.delete(filter={"case_id": cid})
                pine_deleted += 1
            except Exception as exc:
                logger.warning("Pinecone delete failed for %s: %s", cid[:12], exc)
        if (i + 100) % 500 == 0 or i + 100 >= len(delete_ids):
            logger.info("  Pinecone: processed %d/%d case IDs",
                         min(i + 100, len(delete_ids)), len(delete_ids))

    # Also clean up stale vectors from previously deleted cases
    # Get all keep IDs as a set for checking
    set(keep_ids)

    # We can't enumerate all Pinecone vectors efficiently, but we've deleted
    # all vectors for the 2,314 delete_ids. The stale vectors from even older
    # deletions (pre-Mar 26) should also be cleaned, but that requires
    # listing all vector IDs which is expensive. Skip for now.

    stats_after = idx.describe_index_stats()
    logger.info("Pinecone after: %d vectors (removed ~%d)",
                stats_after.total_vector_count,
                stats_before.total_vector_count - stats_after.total_vector_count)

    # ══════════════════════════════════════════════════════════════════
    # STEP 3: Neo4j — delete case nodes not in keep list + stale nodes
    # ══════════════════════════════════════════════════════════════════
    logger.info("=" * 60)
    logger.info("STEP 3: Neo4j — cleaning stale and deleted case nodes")
    logger.info("=" * 60)

    from neo4j import GraphDatabase
    uri = os.environ.get("NEO4J_URI")
    neo_user = os.environ.get("NEO4J_USER")
    pwd = os.environ.get("NEO4J_PASSWORD")
    driver = GraphDatabase.driver(uri, auth=(neo_user, pwd))

    with driver.session() as session:
        # Count before
        result = session.run("MATCH (c:Case) RETURN count(c) as cnt")
        neo_before = result.single()["cnt"]
        logger.info("Neo4j before: %d Case nodes", neo_before)

        # Delete all Case nodes whose id is NOT in keep_ids
        # Neo4j can handle large parameter lists via UNWIND
        # First: delete nodes WITH id that are NOT in keep list
        # Process in batches to avoid memory issues
        neo_deleted = 0
        for i in range(0, len(delete_ids), 500):
            batch = delete_ids[i:i + 500]
            result = session.run(
                "UNWIND $ids AS cid "
                "MATCH (c:Case) WHERE c.id = cid "
                "DETACH DELETE c "
                "RETURN count(c) as cnt",
                ids=batch,
            )
            cnt = result.single()["cnt"]
            neo_deleted += cnt
            logger.info("  Neo4j batch %d: deleted %d nodes (total: %d)",
                         i // 500 + 1, cnt, neo_deleted)

        # Now delete ALL stale nodes (those with id NOT in keep list)
        # These are orphans from even older ingestion runs
        logger.info("  Deleting remaining stale nodes (orphans from old runs)...")
        result = session.run(
            "UNWIND $keep AS kid "
            "WITH collect(kid) AS keepSet "
            "MATCH (c:Case) WHERE c.id IS NOT NULL AND NOT c.id IN keepSet "
            "WITH c LIMIT 5000 "
            "DETACH DELETE c "
            "RETURN count(c) as cnt",
            keep=keep_ids,
        )
        stale_cnt = result.single()["cnt"]
        neo_deleted += stale_cnt
        logger.info("  Stale batch 1: deleted %d", stale_cnt)

        # Repeat until no more stale nodes
        while stale_cnt > 0:
            result = session.run(
                "UNWIND $keep AS kid "
                "WITH collect(kid) AS keepSet "
                "MATCH (c:Case) WHERE c.id IS NOT NULL AND NOT c.id IN keepSet "
                "WITH c LIMIT 5000 "
                "DETACH DELETE c "
                "RETURN count(c) as cnt",
                keep=keep_ids,
            )
            stale_cnt = result.single()["cnt"]
            neo_deleted += stale_cnt
            if stale_cnt > 0:
                logger.info("  Stale batch: deleted %d more", stale_cnt)

        # Count after
        result = session.run("MATCH (c:Case) RETURN count(c) as cnt")
        neo_after = result.single()["cnt"]
        logger.info("Neo4j after: %d Case nodes (deleted %d total)", neo_after, neo_deleted)

    driver.close()

    # ══════════════════════════════════════════════════════════════════
    # SUMMARY
    # ══════════════════════════════════════════════════════════════════
    logger.info("=" * 60)
    logger.info("PURGE COMPLETE")
    logger.info("=" * 60)
    logger.info("PostgreSQL: %d -> %d cases", total_before, total_after)
    logger.info("Pinecone: %d -> %d vectors", stats_before.total_vector_count, stats_after.total_vector_count)
    logger.info("Neo4j: %d -> %d Case nodes", neo_before, neo_after)
    logger.info("Cases kept: %d (verified clean)", len(keep_ids))


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge bad cases from all stores")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()
    asyncio.run(purge(args.dry_run))


if __name__ == "__main__":
    main()
