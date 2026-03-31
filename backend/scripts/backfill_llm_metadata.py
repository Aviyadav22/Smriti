"""Backfill LLM metadata for cases where extraction failed during ingestion.

Targets cases with case_type IS NULL (indicating LLM extraction was skipped
due to rate limits or errors). Re-extracts metadata from existing case_sections
text using the LLM, then updates PostgreSQL and Pinecone metadata.

Usage:
    python scripts/backfill_llm_metadata.py [--limit N] [--concurrency N] [--dry-run]
"""

import argparse
import asyncio
import itertools
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.ingestion.metadata import (  # noqa: E402
    CaseMetadata,
    cross_validate_propositions,
    extract_metadata_llm,
    merge_metadata,
    validate_cross_fields,
    validate_with_regex,
)
from app.core.legal.extractor import (  # noqa: E402
    extract_acts_cited,
    normalize_acts_cited_list,
)
from app.core.legal.statute_enrichment import enrich_statute_cross_references  # noqa: E402
from app.core.providers.llm.gemini import GeminiLLM  # noqa: E402
from app.db.postgres import async_session_factory, engine  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("backfill_llm")


def _build_llm_pool() -> list[GeminiLLM]:
    """Build a pool of LLM clients from GEMINI_API_KEYS."""
    keys_str = getattr(settings, "gemini_api_keys", "") or ""
    if keys_str:
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
    else:
        keys = [settings.gemini_api_key]

    pool = []
    for key in keys:
        pool.append(GeminiLLM(
            api_key=key,
            model=settings.gemini_flash_model,
        ))
    return pool


async def _get_case_text(session, case_id: str) -> str:
    """Reconstruct full text from case_sections."""
    rows = (await session.execute(text(
        "SELECT content FROM case_sections WHERE case_id = :cid ORDER BY section_index"
    ), {"cid": case_id})).fetchall()
    return "\n\n".join(r[0] for r in rows if r[0])


async def _get_parquet_metadata(session, case_id: str) -> dict:
    """Get the parquet-sourced fields from the existing case row."""
    row = (await session.execute(text(
        "SELECT title, citation, court, year, decision_date::text, "
        "petitioner, respondent, author_judge, disposal_nature, judge "
        "FROM cases WHERE id = :cid"
    ), {"cid": case_id})).fetchone()
    if not row:
        return {}
    cols = ["title", "citation", "court", "year", "decision_date",
            "petitioner", "respondent", "author_judge", "disposal_nature", "judge"]
    return {k: v for k, v in zip(cols, row) if v is not None}


async def _update_case_metadata(session, case_id: str, metadata: CaseMetadata,
                                 provenance: dict) -> None:
    """Update the case row with backfilled LLM metadata."""
    update_fields = {
        "case_type": metadata.case_type,
        "ratio_decidendi": metadata.ratio_decidendi,
        "jurisdiction": metadata.jurisdiction,
        "bench_type": metadata.bench_type,
        "keywords": metadata.keywords,
        "headnotes": metadata.headnotes,
        "outcome_summary": metadata.outcome_summary,
        "case_number": metadata.case_number,
        "is_reportable": metadata.is_reportable,
        "coram_size": metadata.coram_size,
        "acts_cited": metadata.acts_cited,
        "cases_cited": metadata.cases_cited,
        "metadata_provenance": json.dumps(provenance),
        "ingestion_status": "complete",
    }

    # Also update judge if LLM extracted more judges
    if metadata.judge and len(metadata.judge) > 1:
        update_fields["judge"] = metadata.judge

    set_clauses = []
    params = {"cid": case_id}
    for field, value in update_fields.items():
        if value is not None:
            if isinstance(value, list):
                params[field] = value
                set_clauses.append(f"{field} = :{field}")
            elif isinstance(value, bool):
                params[field] = value
                set_clauses.append(f"{field} = :{field}")
            else:
                params[field] = value
                set_clauses.append(f"{field} = :{field}")

    if not set_clauses:
        return

    set_clauses.append("updated_at = NOW()")
    sql = f"UPDATE cases SET {', '.join(set_clauses)} WHERE id = :cid"
    await session.execute(text(sql), params)
    await session.commit()


async def backfill_one(case_id: str, llm: GeminiLLM, semaphore: asyncio.Semaphore,
                        dry_run: bool = False) -> str:
    """Backfill LLM metadata for a single case. Returns 'success', 'skipped', or 'failed'."""
    async with semaphore:
        try:
            async with async_session_factory() as session:
                # Get existing text
                full_text = await _get_case_text(session, case_id)
                if not full_text or len(full_text) < 100:
                    logger.warning("Case %s has insufficient text (%d chars), skipping",
                                   case_id, len(full_text) if full_text else 0)
                    return "skipped"

                # Get parquet metadata for merge
                parquet_meta = await _get_parquet_metadata(session, case_id)

                # Extract metadata via LLM (text-only, no PDF)
                llm_meta = await extract_metadata_llm(full_text, llm)

                # Check if LLM actually returned useful data
                if llm_meta.case_type is None and llm_meta.ratio_decidendi is None:
                    logger.warning("LLM returned empty metadata for %s", case_id)
                    return "failed"

                # Merge with parquet
                metadata, provenance = merge_metadata(parquet_meta, llm_meta)

                # Validate
                metadata = validate_with_regex(metadata)
                metadata = validate_cross_fields(metadata)
                metadata = cross_validate_propositions(metadata)

                # Supplement acts_cited with regex
                regex_acts = extract_acts_cited(full_text)
                if regex_acts:
                    llm_acts = set(metadata.acts_cited or [])
                    for ref in regex_acts:
                        act_str = f"{ref.act_name}, {ref.year}" if ref.year else ref.act_name
                        llm_acts.add(act_str)
                    metadata.acts_cited = sorted(llm_acts)

                # Normalize acts
                if metadata.acts_cited:
                    metadata.acts_cited = normalize_acts_cited_list(metadata.acts_cited)
                if metadata.acts_cited:
                    metadata.acts_cited = enrich_statute_cross_references(
                        metadata.acts_cited, decision_year=metadata.year,
                    )

                if dry_run:
                    logger.info("[DRY-RUN] Would update %s: case_type=%s, ratio=%s...",
                                case_id, metadata.case_type,
                                (metadata.ratio_decidendi or "")[:50])
                    return "success"

                # Update PostgreSQL
                await _update_case_metadata(session, case_id, metadata, provenance)
                return "success"

        except Exception as exc:
            logger.error("Failed to backfill %s: %s", case_id, exc)
            return "failed"


async def main():
    parser = argparse.ArgumentParser(description="Backfill LLM metadata for failed cases")
    parser.add_argument("--limit", type=int, default=None, help="Max cases to process")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent LLM calls")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    args = parser.parse_args()

    llm_pool = _build_llm_pool()
    logger.info("Using %d Gemini API key(s) for backfill", len(llm_pool))
    llm_cycle = itertools.cycle(llm_pool)

    # Get cases needing backfill
    async with async_session_factory() as session:
        limit_clause = f"LIMIT {args.limit}" if args.limit else ""
        rows = (await session.execute(text(
            f"SELECT id FROM cases WHERE case_type IS NULL ORDER BY decision_date DESC {limit_clause}"
        ))).fetchall()

    case_ids = [r[0] for r in rows]
    total = len(case_ids)
    logger.info("Found %d cases needing LLM metadata backfill", total)

    if total == 0:
        logger.info("Nothing to backfill!")
        await engine.dispose()
        return

    semaphore = asyncio.Semaphore(args.concurrency)
    stats = {"success": 0, "failed": 0, "skipped": 0}
    start_time = time.time()

    # Process in batches for progress tracking
    batch_size = 50
    for i in range(0, total, batch_size):
        batch = case_ids[i:i + batch_size]
        tasks = [
            backfill_one(cid, next(llm_cycle), semaphore, dry_run=args.dry_run)
            for cid in batch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                stats["failed"] += 1
            else:
                stats[r] += 1

        elapsed = time.time() - start_time
        done = i + len(batch)
        rate = done / (elapsed / 60) if elapsed > 0 else 0
        remaining = (total - done) / rate if rate > 0 else 0
        logger.info(
            "[%d/%d] %.1f%% | %.1f cases/min | ETA: %.0fm | success=%d failed=%d skipped=%d",
            done, total, 100 * done / total, rate, remaining,
            stats["success"], stats["failed"], stats["skipped"],
        )

    logger.info("=== BACKFILL COMPLETE ===")
    logger.info("Stats: %s", stats)
    logger.info("Elapsed: %.1f minutes", (time.time() - start_time) / 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
