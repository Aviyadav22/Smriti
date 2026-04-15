#!/usr/bin/env python3
"""Normalize acts_cited to canonical short codes for all existing cases.

Retroactively applies normalize_acts_cited_list() and
enrich_statute_cross_references() to every case in PostgreSQL, then
optionally re-syncs Pinecone vector metadata.

Usage:
    python -m scripts.normalize_acts_cited          # Dry run (default)
    python -m scripts.normalize_acts_cited --commit  # Actually write changes
    python -m scripts.normalize_acts_cited --commit --sync-pinecone  # + Pinecone
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from collections import Counter

# Ensure the backend package is importable when running as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import text

from app.core.legal.extractor import normalize_acts_cited_list
from app.core.legal.statute_enrichment import enrich_statute_cross_references
from app.db.postgres import async_session_factory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pinecone metadata re-sync
# ---------------------------------------------------------------------------


async def sync_pinecone_metadata(
    updated_cases: list[dict],
) -> dict[str, int]:
    """Update acts_cited metadata on Pinecone vectors for changed cases.

    For each updated case, queries Pinecone for vectors with matching case_id
    and updates their acts_cited metadata field.

    Args:
        updated_cases: list of dicts with keys: id, acts_cited

    Returns:
        Stats dict with vectors_updated, vectors_failed, cases_synced counts.
    """
    stats = {"vectors_updated": 0, "vectors_failed": 0, "cases_synced": 0}

    try:
        from pinecone import Pinecone

        from app.core.config import settings

        if not settings.pinecone_api_key or not settings.pinecone_api_key.strip():
            logger.error("PINECONE_API_KEY not set — cannot sync Pinecone metadata")
            return stats

        client = Pinecone(api_key=settings.pinecone_api_key)
        host = settings.pinecone_host
        if host:
            index = client.Index(host=host)
        else:
            index = client.Index(settings.pinecone_index_name)

    except Exception as exc:
        logger.error("Failed to initialize Pinecone client: %s", exc)
        return stats

    for case in updated_cases:
        case_id = str(case["id"])
        new_acts = case["acts_cited"]

        try:
            # Query for all vectors belonging to this case
            results = index.query(
                vector=[0.0] * 1536,
                top_k=10_000,
                filter={"case_id": case_id},
                include_metadata=False,
            )
            vector_ids = [m.id for m in results.matches]

            if not vector_ids:
                logger.debug("No Pinecone vectors found for case_id=%s", case_id)
                continue

            # Update metadata for each vector
            for vid in vector_ids:
                try:
                    index.update(
                        id=vid,
                        set_metadata={"acts_cited": new_acts},
                    )
                    stats["vectors_updated"] += 1
                except Exception as vec_exc:
                    logger.warning(
                        "Failed to update Pinecone vector %s: %s", vid, vec_exc,
                    )
                    stats["vectors_failed"] += 1

            stats["cases_synced"] += 1

        except Exception as exc:
            logger.error(
                "Pinecone sync failed for case_id=%s: %s", case_id, exc,
            )
            stats["vectors_failed"] += 1

    return stats


# ---------------------------------------------------------------------------
# Main normalization logic
# ---------------------------------------------------------------------------


async def normalize_all_cases(
    commit: bool = False,
    sync_pinecone: bool = False,
) -> None:
    """Normalize acts_cited for all cases in PostgreSQL.

    Args:
        commit: If True, write changes to the database. Otherwise dry-run.
        sync_pinecone: If True and commit is True, also update Pinecone metadata.
    """
    start_time = time.monotonic()
    mode = "COMMIT" if commit else "DRY RUN"
    logger.info("=== Normalize acts_cited — %s mode ===", mode)

    # Counters
    total_processed = 0
    total_changed = 0
    total_unchanged = 0
    acts_normalized: Counter[str] = Counter()  # "old -> new" transitions
    acts_filtered: Counter[str] = Counter()    # garbage removed
    acts_added: Counter[str] = Counter()       # added by enrichment
    updated_cases: list[dict] = []

    async with async_session_factory() as db:
        # Fetch all cases with non-null acts_cited
        result = await db.execute(
            text("SELECT id, title, acts_cited, year FROM cases WHERE acts_cited IS NOT NULL")
        )
        rows = result.fetchall()
        logger.info("Found %d cases with acts_cited", len(rows))

        for row in rows:
            case_id, title, old_acts, case_year = row[0], row[1], row[2], row[3]

            # Skip empty lists
            if not old_acts:
                total_processed += 1
                total_unchanged += 1
                continue

            # Normalize
            normalized = normalize_acts_cited_list(old_acts)
            # Enrich with cross-references (IPC <-> BNS, etc.)
            # Temporal guard: pre-2024 cases won't get new codes (BNS/BNSS/BSA)
            enriched = enrich_statute_cross_references(
                normalized, decision_year=case_year,
            )

            old_set = set(old_acts)
            new_set = set(enriched)

            if old_set == new_set:
                total_processed += 1
                total_unchanged += 1
                continue

            # Track what changed
            removed = old_set - new_set
            added = new_set - old_set

            # Classify changes: removed items are either "normalized" (old
            # form replaced by canonical form) or "filtered" (garbage removed)
            for act in removed:
                # If the normalized version is in the new set, it was normalized
                act_normalized = normalize_acts_cited_list([act])
                if act_normalized and act_normalized[0] in new_set:
                    acts_normalized[f"{act} -> {act_normalized[0]}"] += 1
                else:
                    acts_filtered[act] += 1

            for act in added:
                # Acts added by enrichment (cross-references) vs normalization
                if act not in set(normalized):
                    acts_added[act] += 1

            total_changed += 1
            total_processed += 1

            # Log the change
            short_title = (title[:60] + "...") if title and len(title) > 60 else title
            logger.info(
                "[%d] %s (id=%s)\n  OLD: %s\n  NEW: %s\n  Removed: %s\n  Added: %s",
                total_changed,
                short_title,
                case_id,
                sorted(old_acts),
                sorted(enriched),
                sorted(removed) if removed else "none",
                sorted(added) if added else "none",
            )

            if commit:
                await db.execute(
                    text("UPDATE cases SET acts_cited = :acts WHERE id = :id"),
                    {"acts": enriched, "id": case_id},
                )
                updated_cases.append({"id": case_id, "acts_cited": enriched})

        if commit and updated_cases:
            await db.commit()
            logger.info("Committed %d updates to PostgreSQL", len(updated_cases))

    # -----------------------------------------------------------------------
    # Pinecone sync (optional)
    # -----------------------------------------------------------------------
    if sync_pinecone and commit and updated_cases:
        logger.info("--- Syncing Pinecone metadata for %d cases ---", len(updated_cases))
        pc_stats = await sync_pinecone_metadata(updated_cases)
        logger.info(
            "Pinecone sync: %d vectors updated, %d failed, %d cases synced",
            pc_stats["vectors_updated"],
            pc_stats["vectors_failed"],
            pc_stats["cases_synced"],
        )
    elif sync_pinecone and not commit:
        logger.warning(
            "--sync-pinecone requires --commit to actually update. "
            "Skipping Pinecone sync in dry-run mode."
        )
    elif sync_pinecone and not updated_cases:
        logger.info("No cases changed — Pinecone sync not needed.")

    # -----------------------------------------------------------------------
    # Summary report
    # -----------------------------------------------------------------------
    elapsed = time.monotonic() - start_time
    logger.info("=== SUMMARY (%s) ===", mode)
    logger.info("Total cases processed:   %d", total_processed)
    logger.info("Cases changed:           %d", total_changed)
    logger.info("Cases unchanged:         %d", total_unchanged)
    logger.info("Time elapsed:            %.1fs", elapsed)

    if acts_normalized:
        logger.info("--- Acts normalized (%d unique) ---", len(acts_normalized))
        for act, count in acts_normalized.most_common():
            logger.info("  %s  (x%d)", act, count)

    if acts_filtered:
        logger.info("--- Acts filtered out / garbage removed (%d unique) ---", len(acts_filtered))
        for act, count in acts_filtered.most_common():
            logger.info("  %s  (x%d)", act, count)

    if acts_added:
        logger.info("--- Acts added by enrichment (%d unique) ---", len(acts_added))
        for act, count in acts_added.most_common():
            logger.info("  %s  (x%d)", act, count)

    if not commit and total_changed > 0:
        logger.info(
            "Run with --commit to apply these changes to the database."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize acts_cited to canonical short codes for all existing cases.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually write changes to PostgreSQL (default is dry-run)",
    )
    parser.add_argument(
        "--sync-pinecone",
        action="store_true",
        help="Also update Pinecone vector metadata for changed cases (requires --commit)",
    )
    args = parser.parse_args()

    asyncio.run(normalize_all_cases(commit=args.commit, sync_pinecone=args.sync_pinecone))


if __name__ == "__main__":
    main()
