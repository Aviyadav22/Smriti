#!/usr/bin/env python3
"""Re-embed cases that have PG metadata but are missing Pinecone vectors.

Reads case IDs from a JSON file, loads full_text + sections from PG,
re-chunks, embeds, and upserts to Pinecone. No LLM calls needed.

Usage:
    python scripts/backfill_missing_vectors.py
    python scripts/backfill_missing_vectors.py --input trial_reports/missing_vectors.json
    python scripts/backfill_missing_vectors.py --concurrency 2 --rpm-limit 30
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import asyncpg  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("backfill_vectors")


async def main(
    input_file: str,
    concurrency: int,
    rpm_limit: int,
) -> None:
    # Load missing case IDs
    missing_ids: list[str] = json.loads(Path(input_file).read_text(encoding="utf-8"))
    logger.info("Loaded %d case IDs to re-embed from %s", len(missing_ids), input_file)

    if not missing_ids:
        logger.info("No cases to process")
        return

    # Connect to PG (use pool for concurrent access)
    from app.core.config import settings
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn, min_size=2, max_size=concurrency + 1)

    # Initialize providers
    from app.core.dependencies import get_embedder, get_vector_store
    from app.core.ingestion.chunker import Section, chunk_judgment
    from app.core.ingestion.pipeline import _embed_chunks, _upsert_vectors

    embedder = get_embedder()
    vector_store = get_vector_store()

    # Rate limiter
    from scripts.batch_ingest_vertex import AsyncRateLimiter
    embed_limiter = AsyncRateLimiter(max_per_minute=rpm_limit)

    sem = asyncio.Semaphore(concurrency)
    success = 0
    failed = 0
    skipped = 0

    async def process_one(case_id: str) -> None:
        nonlocal success, failed, skipped
        async with sem:
            try:
                # Fetch from PG
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT id, title, citation, court, year, case_type, "
                        "bench_type, disposal_nature, jurisdiction, full_text "
                        "FROM cases WHERE id = $1::uuid",
                        case_id,
                    )
                    if not row:
                        logger.warning("Case %s not found in PG, skipping", case_id[:12])
                        skipped += 1
                        return

                    full_text = row["full_text"]
                    if not full_text or len(full_text) < 100:
                        logger.warning("Case %s has no/short text, skipping", case_id[:12])
                        skipped += 1
                        return

                    # Get sections
                    section_rows = await conn.fetch(
                        "SELECT section_type, content, section_index "
                        "FROM case_sections WHERE case_id = $1::uuid ORDER BY section_index",
                        case_id,
                    )
                sections = [
                    Section(
                        type=sr["section_type"],
                        start=sr["section_index"] * 1000,
                        end=(sr["section_index"] + 1) * 1000,
                        text=sr["content"],
                    )
                    for sr in section_rows
                ]

                # Chunk
                chunks = chunk_judgment(full_text, sections, case_id=case_id)
                if not chunks:
                    logger.warning("Case %s produced 0 chunks, skipping", case_id[:12])
                    skipped += 1
                    return

                # Embed
                texts = [c.text for c in chunks]
                embeddings = await _embed_chunks(
                    chunks, embedder, rate_limiter=embed_limiter,
                    texts_override=texts,
                )

                if len(embeddings) != len(chunks):
                    logger.error(
                        "Case %s: embedding count mismatch (%d vs %d)",
                        case_id[:12], len(embeddings), len(chunks),
                    )
                    failed += 1
                    return

                # Build metadata for vectors
                from app.core.ingestion.metadata import CaseMetadata
                metadata = CaseMetadata(
                    title=row["title"],
                    citation=row["citation"],
                    court=row["court"],
                    year=row["year"],
                    case_type=row["case_type"],
                    bench_type=row["bench_type"],
                    disposal_nature=row["disposal_nature"],
                    jurisdiction=row["jurisdiction"],
                )

                # Upsert to Pinecone
                await _upsert_vectors(
                    case_id, chunks, embeddings, metadata, vector_store,
                    full_text=full_text,
                )

                success += 1
                if success % 20 == 0:
                    logger.info(
                        "Progress: %d success, %d failed, %d skipped (of %d)",
                        success, failed, skipped, len(missing_ids),
                    )

            except Exception as exc:
                logger.error("Case %s failed: %s", case_id[:12], exc)
                failed += 1

    # Process all
    tasks = [process_one(cid) for cid in missing_ids]
    await asyncio.gather(*tasks)

    await pool.close()

    logger.info(
        "COMPLETE: %d success, %d failed, %d skipped (of %d total)",
        success, failed, skipped, len(missing_ids),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-embed cases missing Pinecone vectors")
    parser.add_argument(
        "--input", default="trial_reports/missing_vectors.json",
        help="JSON file with case ID list",
    )
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--rpm-limit", type=int, default=60, help="Embedding RPM")
    args = parser.parse_args()
    asyncio.run(main(args.input, args.concurrency, args.rpm_limit))
