#!/usr/bin/env python3
"""Re-ingest the 379 trial cases (1979-2018) after pipeline quality fixes.

Usage:
    # Dry run — show what would be deleted
    python -m scripts.reingest_trial_cases --dry-run

    # Delete corrupted data
    python -m scripts.reingest_trial_cases --delete

    # Re-ingest with fixed pipeline (after deletion)
    python -m scripts.reingest_trial_cases --reingest
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Trial run metadata — adjust these to match your actual trial batch
TRIAL_YEARS = range(1979, 2019)  # 1979-2018 inclusive


async def find_trial_cases(db_url: str) -> list[str]:
    """Find case IDs from the trial batch run."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(db_url)
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT id, title, year FROM cases "
                "WHERE year >= :min_year AND year <= :max_year "
                "ORDER BY year, title"
            ),
            {"min_year": min(TRIAL_YEARS), "max_year": max(TRIAL_YEARS)},
        )
        rows = result.fetchall()
        logger.info("Found %d cases in year range %d-%d", len(rows), min(TRIAL_YEARS), max(TRIAL_YEARS))
        return [str(row[0]) for row in rows]


async def delete_from_postgres(db_url: str, case_ids: list[str]) -> int:
    """Delete trial cases from PostgreSQL."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("DELETE FROM cases WHERE id = ANY(:ids)"),
            {"ids": case_ids},
        )
        count = result.rowcount
        logger.info("Deleted %d cases from PostgreSQL", count)
        return count


async def delete_from_pinecone(case_ids: list[str]) -> int:
    """Delete vectors for trial cases from Pinecone."""
    from pinecone import Pinecone

    from app.core.config import settings

    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(host=settings.pinecone_host)

    deleted = 0
    for i in range(0, len(case_ids), 10):
        batch = case_ids[i:i + 10]
        for cid in batch:
            index.delete(filter={"case_id": cid})
            deleted += 1
        logger.info("Pinecone: deleted vectors for %d/%d cases", deleted, len(case_ids))

    return deleted


async def delete_from_neo4j(case_ids: list[str]) -> int:
    """Delete case nodes and edges from Neo4j."""
    from neo4j import AsyncGraphDatabase

    from app.core.config import settings

    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    async with driver.session() as session:
        result = await session.run(
            "UNWIND $ids AS cid "
            "MATCH (c:Case {case_id: cid}) "
            "DETACH DELETE c "
            "RETURN count(c) AS deleted",
            ids=case_ids,
        )
        record = await result.single()
        count = record["deleted"] if record else 0
        logger.info("Deleted %d case nodes from Neo4j", count)
    await driver.close()
    return count


async def main() -> None:
    parser = argparse.ArgumentParser(description="Re-ingest trial cases after pipeline quality fixes")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    parser.add_argument("--delete", action="store_true", help="Delete corrupted trial data")
    parser.add_argument("--reingest", action="store_true", help="Show re-ingestion instructions")
    parser.add_argument("--db-url", default=None, help="Database URL override")
    args = parser.parse_args()

    if not any([args.dry_run, args.delete, args.reingest]):
        parser.print_help()
        return

    from app.core.config import settings
    db_url = args.db_url or settings.database_url

    case_ids = await find_trial_cases(db_url)

    if args.dry_run:
        logger.info("DRY RUN: Would delete %d cases:", len(case_ids))
        for cid in case_ids[:10]:
            logger.info("  %s", cid)
        if len(case_ids) > 10:
            logger.info("  ... and %d more", len(case_ids) - 10)
        return

    if args.delete:
        logger.info("Deleting %d trial cases from all stores...", len(case_ids))
        pg = await delete_from_postgres(db_url, case_ids)
        pc = await delete_from_pinecone(case_ids)
        neo = await delete_from_neo4j(case_ids)
        logger.info("Deletion complete: PG=%d, Pinecone=%d, Neo4j=%d", pg, pc, neo)

        # Save deleted IDs for reference
        deleted_path = Path("trial_deleted_ids.json")
        deleted_path.write_text(json.dumps(case_ids, indent=2))
        logger.info("Saved deleted IDs to %s", deleted_path)

    if args.reingest:
        logger.info(
            "Re-ingestion should be run via batch_ingest_vertex.py or ingest_s3.py "
            "with the fixed pipeline. Use --years 1979-2018 --batch-size 50"
        )


if __name__ == "__main__":
    asyncio.run(main())
