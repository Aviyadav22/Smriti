"""Repair ingestion data quality issues found in the March 2026 audit.

Fixes:
  1. Rebuild FTS tsvectors (searchable_text) for all cases
  2. Clean acts_cited garbage entries (sentence fragments, hallucinations)
  3. Update Pinecone vector metadata: replace empty strings with None
  4. Re-enable FTS trigger if disabled

Usage:
    python scripts/repair_ingestion_data.py [--fix-fts] [--fix-acts] [--fix-pinecone] [--all]
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.legal.extractor import normalize_acts_cited_list  # noqa: E402
from app.db.postgres import async_session_factory, engine  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("repair_data")


# ---------------------------------------------------------------------------
# 1. FTS rebuild
# ---------------------------------------------------------------------------

async def rebuild_fts():
    """Rebuild searchable_text tsvector for all cases with NULL searchable_text."""
    logger.info("=== Rebuilding FTS tsvectors ===")
    async with async_session_factory() as session:
        # Count cases needing rebuild
        count = (await session.execute(text(
            "SELECT count(*) FROM cases WHERE searchable_text IS NULL"
        ))).scalar()
        logger.info("Cases needing FTS rebuild: %d", count)

        if count == 0:
            logger.info("No cases need FTS rebuild")
            return

        # Batch rebuild in chunks of 500
        batch_size = 500
        total_updated = 0
        while True:
            result = await session.execute(text("""
                UPDATE cases SET searchable_text = to_tsvector('english',
                    coalesce(title, '') || ' ' ||
                    coalesce(petitioner, '') || ' ' ||
                    coalesce(respondent, '') || ' ' ||
                    coalesce(court, '') || ' ' ||
                    coalesce(case_type, '') || ' ' ||
                    coalesce(ratio_decidendi, '') || ' ' ||
                    coalesce(outcome_summary, '') || ' ' ||
                    coalesce(array_to_string(keywords, ' '), '') || ' ' ||
                    coalesce(array_to_string(acts_cited, ' '), '') || ' ' ||
                    coalesce(array_to_string(judge, ' '), '')
                )
                WHERE id IN (
                    SELECT id FROM cases WHERE searchable_text IS NULL LIMIT :batch
                )
            """), {"batch": batch_size})
            updated = result.rowcount
            await session.commit()
            total_updated += updated
            logger.info("FTS rebuild: %d/%d done", total_updated, count)
            if updated < batch_size:
                break

        # Re-enable FTS trigger
        try:
            await session.execute(text(
                "ALTER TABLE cases ENABLE TRIGGER cases_searchable_text_trigger"
            ))
            await session.commit()
            logger.info("FTS trigger re-enabled")
        except Exception as exc:
            logger.warning("Could not re-enable FTS trigger (may not exist): %s", exc)

    logger.info("FTS rebuild complete: %d cases updated", total_updated)


# ---------------------------------------------------------------------------
# 2. Clean acts_cited
# ---------------------------------------------------------------------------

async def clean_acts_cited():
    """Re-normalize acts_cited for all cases to remove garbage entries."""
    logger.info("=== Cleaning acts_cited garbage entries ===")
    async with async_session_factory() as session:
        # Get all cases with acts_cited
        rows = (await session.execute(text(
            "SELECT id, acts_cited FROM cases WHERE acts_cited IS NOT NULL"
        ))).fetchall()
        logger.info("Cases with acts_cited: %d", len(rows))

        updated = 0
        cleaned_total = 0
        for case_id, acts in rows:
            if not acts:
                continue
            original_count = len(acts)
            cleaned = normalize_acts_cited_list(acts)
            if cleaned != acts:
                diff = original_count - len(cleaned)
                cleaned_total += diff
                await session.execute(text(
                    "UPDATE cases SET acts_cited = :acts WHERE id = :cid"
                ), {"acts": cleaned if cleaned else None, "cid": case_id})
                updated += 1

        await session.commit()
        logger.info("Acts cleanup: %d cases updated, %d garbage entries removed", updated, cleaned_total)


# ---------------------------------------------------------------------------
# 3. Fix Pinecone empty strings
# ---------------------------------------------------------------------------

async def fix_pinecone_empty_strings():
    """Replace empty string metadata values with None in Pinecone vectors."""
    logger.info("=== Fixing Pinecone empty string metadata ===")
    from pinecone import Pinecone

    pc = Pinecone(api_key=settings.pinecone_api_key)
    idx = pc.Index(host=settings.pinecone_host)

    stats = idx.describe_index_stats()
    total_vectors = stats.total_vector_count
    logger.info("Total Pinecone vectors: %d", total_vectors)

    # Fields that should not be empty strings
    metadata_fields = [
        "case_type", "jurisdiction", "bench_type", "disposal_nature",
        "judicial_tone", "court",
    ]

    # We need to fetch vectors in batches and update metadata
    # Pinecone doesn't support bulk metadata-only updates easily,
    # so we'll query for vectors with empty strings and update them

    # Get all case IDs from PG
    async with async_session_factory() as session:
        case_ids = (await session.execute(text(
            "SELECT id FROM cases"
        ))).fetchall()
    case_ids = [r[0] for r in case_ids]

    updated_count = 0
    batch_size = 100

    for i in range(0, len(case_ids), batch_size):
        batch_ids = case_ids[i:i + batch_size]
        # Fetch vectors for these cases
        for case_id in batch_ids:
            try:
                # Query vectors for this case
                results = idx.query(
                    vector=[0.0] * 1536,  # dummy vector
                    filter={"case_id": str(case_id)},
                    top_k=200,
                    include_metadata=True,
                )
                for match in results.matches:
                    meta = match.metadata or {}
                    updates = {}
                    for field in metadata_fields:
                        if field in meta and meta[field] == "":
                            updates[field] = None

                    if updates:
                        new_meta = {**meta, **updates}
                        # Remove None values (Pinecone doesn't store None, just omit the key)
                        new_meta = {k: v for k, v in new_meta.items() if v is not None}
                        idx.update(id=match.id, set_metadata=new_meta)
                        updated_count += 1

            except Exception as exc:
                logger.warning("Failed to update vectors for case %s: %s", case_id, str(exc)[:80])

        if (i + batch_size) % 500 == 0:
            logger.info("Pinecone cleanup progress: %d/%d cases checked, %d vectors updated",
                        min(i + batch_size, len(case_ids)), len(case_ids), updated_count)

    logger.info("Pinecone cleanup complete: %d vectors updated", updated_count)


async def main():
    parser = argparse.ArgumentParser(description="Repair ingestion data quality issues")
    parser.add_argument("--fix-fts", action="store_true", help="Rebuild FTS tsvectors")
    parser.add_argument("--fix-acts", action="store_true", help="Clean acts_cited garbage")
    parser.add_argument("--fix-pinecone", action="store_true", help="Fix Pinecone empty strings")
    parser.add_argument("--all", action="store_true", help="Run all fixes")
    args = parser.parse_args()

    if not any([args.fix_fts, args.fix_acts, args.fix_pinecone, args.all]):
        parser.print_help()
        return

    start = time.time()

    if args.all or args.fix_acts:
        await clean_acts_cited()

    if args.all or args.fix_fts:
        await rebuild_fts()

    if args.all or args.fix_pinecone:
        await fix_pinecone_empty_strings()

    elapsed = time.time() - start
    logger.info("All repairs complete in %.1f minutes", elapsed / 60)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
