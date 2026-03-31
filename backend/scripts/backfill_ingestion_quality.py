#!/usr/bin/env python3
"""Backfill ingestion quality fixes for existing cases.

Idempotent script that applies all quality improvements from the ingestion
pipeline audit WITHOUT re-running LLM extraction or re-embedding. Fixes:

1. Strip newlines from cases_cited entries, collapse double-spaces
2. Remove self-citations from cases_cited
3. Remove bare docket numbers from cases_cited
4. Re-normalize acts_cited via improved garbage filter
5. Temporal guard: strip BNS/BNSS/BSA from pre-2024 cases
6. Infer is_reportable from SCR citation pattern
7. Infer bench_type from coram_size
8. Append author_judge to judge array if missing and coram_size > len(judge)
9. Re-apply disposal_nature normalization

Usage:
    python scripts/backfill_ingestion_quality.py --dry-run          # Preview changes
    python scripts/backfill_ingestion_quality.py                    # Apply changes
    python scripts/backfill_ingestion_quality.py --limit 50         # First 50 cases
    python scripts/backfill_ingestion_quality.py --batch-size 200   # Larger batches
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import asyncpg
from sqlalchemy import text

from app.core.legal.extractor import normalize_acts_cited_list
from app.core.legal.statute_enrichment import enrich_statute_cross_references
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_ingestion_quality")


# ---------------------------------------------------------------------------
# Disposal nature normalization (same as validate_parquet_data)
# ---------------------------------------------------------------------------
_DISPOSAL_MAP: dict[str, str] = {
    "appeal(s) allowed": "Allowed",
    "appeals allowed": "Allowed",
    "case allowed": "Allowed",
    "leave granted & allowed": "Allowed",
    "dismissed": "Dismissed",
    "disposed off": "Disposed Of",
    "disposed of": "Disposed Of",
    "case partly allowed": "Partly Allowed",
    "partly allowed": "Partly Allowed",
    "directions issued": "Disposed Of",
    "leave granted & dismissed": "Dismissed",
    "leave granted & disposed off": "Disposed Of",
    "matter referred to larger bench": "Referred to Larger Bench",
    "referred to larger bench": "Referred to Larger Bench",
    "remitted to lower court": "Remanded",
    "rejected": "Dismissed",
    "withdrawn": "Withdrawn",
    "settled": "Settled",
    "transferred": "Transferred",
    "modified": "Modified",
    "abated": "Abated",
    "not pressed": "Not Pressed",
}

_VALID_DISPOSALS = {
    "Allowed", "Dismissed", "Partly Allowed", "Withdrawn", "Remanded",
    "Disposed Of", "Settled", "Transferred", "Modified", "Other",
    "Referred to Larger Bench", "Abated", "Not Pressed",
}

_CORAM_BENCH_MAP = {
    1: "single",
    2: "division",
    3: "full",
    4: "full",
}


def _clean_list_items(items: list[str]) -> list[str]:
    """Strip newlines, collapse double-spaces, deduplicate."""
    seen: dict[str, None] = {}
    for item in items:
        if not isinstance(item, str) or not item.strip():
            continue
        cleaned = item.replace("\n", " ").replace("\r", " ")
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        if cleaned and cleaned not in seen:
            seen[cleaned] = None
    return list(seen.keys())


def fix_case(row: dict) -> dict[str, object]:
    """Apply all quality fixes to a single case row. Returns dict of changed fields."""
    changes: dict[str, object] = {}

    case_id = row["id"]
    year = row["year"]
    citation = row.get("citation") or ""
    acts_cited = row.get("acts_cited") or []
    cases_cited = row.get("cases_cited") or []
    judge = row.get("judge") or []
    author_judge = row.get("author_judge") or ""
    coram_size = row.get("coram_size")
    bench_type = row.get("bench_type")
    is_reportable = row.get("is_reportable")
    disposal_nature = row.get("disposal_nature")

    # 1. Strip newlines from cases_cited
    if cases_cited:
        cleaned_cases = _clean_list_items(cases_cited)
        if cleaned_cases != cases_cited:
            cases_cited = cleaned_cases
            changes["cases_cited"] = cleaned_cases

    # 2. Remove self-citations
    if cases_cited and citation:
        own_norm = re.sub(r"\s+", " ", citation.strip().lower())
        filtered = [
            c for c in cases_cited
            if re.sub(r"\s+", " ", c.strip().lower()) != own_norm
        ]
        if len(filtered) != len(cases_cited):
            cases_cited = filtered
            changes["cases_cited"] = filtered or None

    # 3. Remove bare docket numbers
    if cases_cited:
        filtered = [
            c for c in cases_cited
            if not re.match(r"^\d{3,5}\s+[Oo]f\s+\d{4}$", c.strip())
        ]
        if len(filtered) != len(cases_cited):
            cases_cited = filtered
            changes["cases_cited"] = filtered or None

    # 4. Re-normalize acts_cited
    if acts_cited:
        normalized = normalize_acts_cited_list(acts_cited)
        if set(normalized) != set(acts_cited):
            acts_cited = normalized
            changes["acts_cited"] = normalized

    # 5. Temporal guard: enrich with decision_year
    if acts_cited:
        enriched = enrich_statute_cross_references(acts_cited, decision_year=year)
        if set(enriched) != set(acts_cited):
            acts_cited = enriched
            changes["acts_cited"] = enriched

    # 6. Infer is_reportable from SCR citation
    if is_reportable is None and citation:
        if re.search(r"\[\d{4}\]\s+\d+\s+S\.?C\.?R\.?\s+\d+", citation):
            changes["is_reportable"] = True

    # 7. Infer bench_type from coram_size
    if coram_size and isinstance(coram_size, int):
        inferred = _CORAM_BENCH_MAP.get(coram_size)
        if coram_size >= 5:
            inferred = "constitutional"
        if inferred and bench_type != inferred:
            changes["bench_type"] = inferred

    # 8. Judge array completion
    if (coram_size and judge and author_judge
            and isinstance(coram_size, int)
            and coram_size > len(judge)):
        if author_judge.lower() not in [j.lower() for j in judge]:
            new_judge = judge + [author_judge]
            changes["judge"] = new_judge

    # 9. Disposal nature normalization
    if disposal_nature and disposal_nature not in _VALID_DISPOSALS:
        mapped = _DISPOSAL_MAP.get(disposal_nature.strip().lower())
        if mapped:
            changes["disposal_nature"] = mapped
        elif disposal_nature.title() in _VALID_DISPOSALS:
            changes["disposal_nature"] = disposal_nature.title()

    return changes


def _get_dsn() -> str:
    """Convert SQLAlchemy URL to asyncpg DSN."""
    url = settings.database_url
    # SQLAlchemy uses postgresql+asyncpg://, asyncpg wants postgresql://
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def backfill(
    dry_run: bool = True,
    limit: int | None = None,
    batch_size: int = 100,
) -> None:
    """Run the backfill using raw asyncpg for speed."""
    stats: Counter[str] = Counter()

    dsn = _get_dsn()
    conn = await asyncpg.connect(dsn, timeout=30)

    try:
        # Phase 1: Read all rows
        query = """
            SELECT id, year, citation, acts_cited, cases_cited,
                   judge, author_judge, coram_size, bench_type,
                   is_reportable, disposal_nature
            FROM cases
            ORDER BY year, id
        """
        if limit:
            query += f" LIMIT {limit}"
        rows = await conn.fetch(query)
        total = len(rows)
        logger.info("Loaded %d cases", total)

        # Phase 2: Compute changes (no DB needed)
        update_args: list[tuple] = []
        changed_count = 0
        for row in rows:
            row_dict = dict(row)
            changes = fix_case(row_dict)
            if not changes:
                stats["unchanged"] += 1
                continue
            changed_count += 1
            for field in changes:
                stats[f"{field}_fixed"] += 1
            if dry_run:
                if changed_count <= 20:
                    logger.info(
                        "[DRY-RUN] Case %s (year=%s): %s",
                        row["id"], row["year"],
                        {k: (f"[{len(v)} items]" if isinstance(v, list) else v) for k, v in changes.items()},
                    )
            else:
                # Positional args: acts, cases, judge, bench, reportable, disposal, id
                acts = changes.get("acts_cited", row["acts_cited"] or [])
                cases = changes.get("cases_cited") if "cases_cited" in changes else (row["cases_cited"] or [])
                judge = changes.get("judge", row["judge"] or [])
                bench = changes.get("bench_type", row["bench_type"])
                reportable = changes.get("is_reportable", row["is_reportable"])
                disposal = changes.get("disposal_nature", row["disposal_nature"])
                # Handle None for cases_cited
                if cases is None:
                    cases = []
                update_args.append((acts, cases, judge, bench, reportable, disposal, row["id"]))

        if dry_run or not update_args:
            pass
        else:
            # Phase 3: Write in small batches, reconnect per batch to avoid timeout
            logger.info("Writing %d updates...", len(update_args))
            await conn.close()  # Close read connection

            update_sql = """
                UPDATE cases SET
                    acts_cited = $1,
                    cases_cited = $2,
                    judge = $3,
                    bench_type = $4,
                    is_reportable = $5,
                    disposal_nature = $6
                WHERE id = $7
            """
            logger.info("Connecting for writes...")
            wconn = await asyncpg.connect(dsn, timeout=60)
            logger.info("Connected. Executing updates...")
            try:
                for i, args in enumerate(update_args):
                    if i < 3:
                        logger.info("  Executing row %d (id=%s)...", i, args[-1])
                    await wconn.execute(update_sql, *args)
                    if i < 3:
                        logger.info("  Row %d done", i)
                    if (i + 1) % 50 == 0:
                        logger.info("Progress: %d/%d updates written", i + 1, len(update_args))
            finally:
                await wconn.close()
            conn = None  # Already closed
    finally:
        if conn and not conn.is_closed():
            await conn.close()

    logger.info("=" * 60)
    logger.info("SUMMARY%s", " (DRY-RUN)" if dry_run else "")
    logger.info("Total cases: %d", total)
    logger.info("Changed: %d", changed_count)
    logger.info("Unchanged: %d", stats["unchanged"])
    for key, count in sorted(stats.items()):
        if key != "unchanged":
            logger.info("  %s: %d", key, count)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill ingestion quality fixes")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cases to process")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for DB writes")
    args = parser.parse_args()

    start = time.time()
    asyncio.run(backfill(dry_run=args.dry_run, limit=args.limit, batch_size=args.batch_size))
    elapsed = time.time() - start
    logger.info("Completed in %.1f seconds", elapsed)


if __name__ == "__main__":
    main()
