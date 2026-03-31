#!/usr/bin/env python3
"""Post-ingestion metadata cleanup for cases in the database.

Re-runs the GAN discriminator, OCR repair, and cross-field validation
on existing cases WITHOUT re-extracting from PDFs.

Fixes:
- acts_cited: OCR repair + discriminator filtering
- cases_cited: GAN discriminator (bare refs -> citation_refs)
- title: OCR artifact repair ("0F" -> "OF", etc.)
- case_type vs case_number consistency

Usage:
    python scripts/cleanup_metadata.py                    # all cases from today
    python scripts/cleanup_metadata.py --since 2026-03-31
    python scripts/cleanup_metadata.py --dry-run          # preview changes
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import asyncpg  # noqa: E402
import os  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("cleanup_metadata")


def _get_dsn() -> str:
    from app.core.config import settings
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


def fix_title_ocr(title: str | None) -> str | None:
    """Fix common OCR artifacts in case titles."""
    if not title:
        return title
    import re
    # "0F" -> "OF" (zero instead of O)
    fixed = re.sub(r"\b0F\b", "OF", title)
    # "1N" -> "IN" (one instead of I)
    fixed = re.sub(r"\b1N\b", "IN", fixed)
    # "0R" -> "OR"
    fixed = re.sub(r"\b0R\b", "OR", fixed)
    # "0N" -> "ON"
    fixed = re.sub(r"\b0N\b", "ON", fixed)
    # Double spaces
    fixed = re.sub(r"\s{2,}", " ", fixed).strip()
    return fixed if fixed != title else title


def fix_acts_cited(acts: list[str] | None) -> list[str] | None:
    """Re-run OCR repair + normalization on acts_cited."""
    if not acts:
        return acts
    from app.core.legal.extractor import normalize_acts_cited_list
    result = normalize_acts_cited_list(acts)
    return result if result else None


def fix_cases_cited(cases: list[str] | None) -> tuple[list[str] | None, list[str] | None]:
    """Re-run GAN discriminator on cases_cited.

    Returns (named_citations, bare_refs).
    """
    if not cases:
        return cases, None
    from app.core.legal.extractor import classify_case_citations
    named, bare = classify_case_citations(cases)
    return (named if named else None), (bare if bare else None)


def fix_case_type_vs_number(
    case_type: str | None, case_number: str | None,
) -> str | None:
    """Correct case_type based on case_number."""
    import re
    if not case_number or not case_type:
        return case_type
    cn_lower = case_number.lower()
    if "civil appeal" in cn_lower and case_type == "Criminal Appeal":
        return "Civil Appeal"
    if "criminal appeal" in cn_lower and case_type == "Civil Appeal":
        return "Criminal Appeal"
    if (re.search(r"slp\s*\(\s*c\s*\)", cn_lower) or "w.p.(c)" in cn_lower):
        if case_type == "Criminal Appeal":
            return "Special Leave Petition" if "slp" in cn_lower else "Writ Petition"
    return case_type


async def cleanup(since: date, dry_run: bool) -> None:
    dsn = _get_dsn()
    conn = await asyncpg.connect(dsn)

    rows = await conn.fetch(
        "SELECT id, title, citation, case_type, case_number, "
        "acts_cited, cases_cited "
        "FROM cases WHERE created_at >= $1 ORDER BY year",
        since,
    )
    logger.info("Found %d cases to clean up", len(rows))

    modified = 0
    details: list[dict] = []

    for row in rows:
        case_id = str(row["id"])
        changes: dict[str, tuple] = {}  # field -> (old, new)

        # 1. Title OCR fix
        old_title = row["title"]
        new_title = fix_title_ocr(old_title)
        if new_title != old_title:
            changes["title"] = (old_title, new_title)

        # 2. Acts cited cleanup
        old_acts = row["acts_cited"]
        new_acts = fix_acts_cited(old_acts)
        if old_acts and new_acts != old_acts:
            # Sort both for comparison
            old_sorted = sorted(old_acts) if old_acts else []
            new_sorted = sorted(new_acts) if new_acts else []
            if old_sorted != new_sorted:
                changes["acts_cited"] = (old_acts, new_acts)

        # 3. Cases cited GAN discriminator
        old_cases = row["cases_cited"]
        new_cases, bare_refs = fix_cases_cited(old_cases)
        if old_cases and (new_cases != old_cases or bare_refs):
            changes["cases_cited"] = (old_cases, new_cases)
            if bare_refs:
                changes["citation_refs"] = (None, bare_refs)

        # 4. Case type vs case number
        old_type = row["case_type"]
        new_type = fix_case_type_vs_number(old_type, row["case_number"])
        if new_type != old_type:
            changes["case_type"] = (old_type, new_type)

        if changes:
            modified += 1
            title_short = (row["title"] or "")[:60]
            detail = {
                "id": case_id,
                "title": title_short,
                "changes": {k: {"old": v[0], "new": v[1]} for k, v in changes.items()},
            }
            details.append(detail)

            logger.info("--- %s: %s ---", case_id[:12], title_short)
            for field, (old_val, new_val) in changes.items():
                if field in ("acts_cited", "cases_cited", "citation_refs"):
                    old_count = len(old_val) if old_val else 0
                    new_count = len(new_val) if new_val else 0
                    removed = set(old_val or []) - set(new_val or []) if field != "citation_refs" else set()
                    logger.info(
                        "  %s: %d -> %d%s",
                        field, old_count, new_count,
                        f" (removed: {removed})" if removed else "",
                    )
                else:
                    logger.info("  %s: %r -> %r", field, old_val, new_val)

            if not dry_run:
                # Build UPDATE query (skip citation_refs — not a DB column yet)
                set_clauses = []
                params = []
                param_idx = 1

                for field, (_, new_val) in changes.items():
                    if field == "citation_refs":
                        continue  # Not a DB column
                    param_idx += 1
                    set_clauses.append(f"{field} = ${param_idx}")
                    params.append(new_val)

                if set_clauses:
                    query = f"UPDATE cases SET {', '.join(set_clauses)} WHERE id = $1"
                    await conn.execute(query, row["id"], *params)

    if not dry_run and modified > 0:
        logger.info("Committed %d case updates", modified)

    logger.info(
        "\n=== SUMMARY ===\n"
        "Total cases: %d\n"
        "Modified: %d\n"
        "Unchanged: %d\n"
        "Mode: %s",
        len(rows), modified, len(rows) - modified,
        "DRY RUN" if dry_run else "APPLIED",
    )

    await conn.close()

    # Save report
    report_path = Path("trial_reports") / f"cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(
        json.dumps({"total": len(rows), "modified": modified, "details": details}, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Report saved to %s", report_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-ingestion metadata cleanup")
    parser.add_argument("--since", type=str, default="2026-03-31", help="Cleanup cases since date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()

    since = date.fromisoformat(args.since)
    asyncio.run(cleanup(since, args.dry_run))


if __name__ == "__main__":
    main()
