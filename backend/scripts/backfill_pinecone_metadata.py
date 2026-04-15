#!/usr/bin/env python3
"""Backfill Pinecone metadata with document_type field.

Adds document_type: "case_law" to all existing vectors that don't have it.
This enables document_type filtering for statute/constitution workers.

Usage:
    python scripts/backfill_pinecone_metadata.py --dry-run
    python scripts/backfill_pinecone_metadata.py
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.db.postgres import async_session_factory

logger = logging.getLogger(__name__)


async def main(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Get all case IDs
    async with async_session_factory() as db:
        result = await db.execute(
            text("SELECT id, chunk_count FROM cases WHERE chunk_count > 0 ORDER BY created_at")
        )
        cases = [(str(row[0]), row[1]) for row in result.fetchall()]

    logger.info("Found %d cases with vectors", len(cases))

    if args.dry_run:
        total_vectors = sum(c[1] for c in cases)
        logger.info("[DRY RUN] Would update %d vectors across %d cases", total_vectors, len(cases))
        return

    try:
        from app.core.dependencies import get_vector_store
        vector_store = get_vector_store()
    except Exception as exc:
        logger.error("Failed to initialize vector store: %s", exc)
        return

    updated = 0
    errors = 0

    for case_id, chunk_count in cases:
        try:
            # Update metadata for each vector belonging to this case
            vector_ids = [f"{case_id}_{i}" for i in range(chunk_count)]
            # Pinecone update: add document_type to metadata
            for vid in vector_ids:
                try:
                    await vector_store.update_metadata(vid, {"document_type": "case_law"})
                    updated += 1
                except Exception:
                    errors += 1
        except Exception as exc:
            logger.error("Failed to update case %s: %s", case_id, exc)
            errors += 1

        if (updated + errors) % 1000 == 0:
            logger.info("Progress: %d updated, %d errors", updated, errors)

    logger.info("=== BACKFILL COMPLETE: %d updated, %d errors ===", updated, errors)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill Pinecone document_type metadata")
    parser.add_argument("--dry-run", action="store_true", help="Count only, no writes")
    asyncio.run(main(parser.parse_args()))
