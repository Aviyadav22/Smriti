#!/usr/bin/env python3
"""Resume Phase 3 processing from saved batch results.

Reads manifest + metadata_results from a completed batch run directory
and processes cases through Phase 3 (chunk, embed, store, graph).

Usage:
    python scripts/resume_phase3.py trial_mega_20260331_182905
    python scripts/resume_phase3.py trial_mega_20260331_182905 --concurrency 2
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

from scripts.batch_ingest_vertex import (
    BATCH_RUNS_DIR,
    ManifestEntry,
    phase3_process_cases,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("resume_phase3")


async def main(run_id: str, rpm_limit: int, concurrency: int) -> None:
    run_dir = BATCH_RUNS_DIR / run_id

    manifest_path = run_dir / "manifest.json"
    results_path = run_dir / "metadata_results.json"
    texts_dir = run_dir / "texts"

    if not manifest_path.exists():
        logger.error("No manifest.json in %s", run_dir)
        return
    if not results_path.exists():
        logger.error("No metadata_results.json in %s", run_dir)
        return

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    metadata_results = json.loads(results_path.read_text(encoding="utf-8"))
    logger.info("Loaded %d manifest entries, %d metadata results", len(manifest_data), len(metadata_results))

    # Build ManifestEntry objects
    entries: list[ManifestEntry] = []
    for entry in manifest_data:
        case_id = entry["case_id"]
        text_path = texts_dir / f"{case_id}.txt"
        full_text = text_path.read_text(encoding="utf-8") if text_path.exists() else ""
        if not full_text:
            logger.warning("No text for case %s, skipping", case_id)
            continue
        me = ManifestEntry(
            case_id=entry["case_id"],
            pdf_local_path=entry["pdf_local_path"],
            gcs_pdf_uri=entry["gcs_pdf_uri"],
            text_hash=entry["text_hash"],
            quality_tier=entry["quality_tier"],
            page_count=entry["page_count"],
            page_map=entry.get("page_map"),
            char_count=entry["char_count"],
            parquet_meta=entry["parquet_meta"],
            full_text=full_text,
        )
        entries.append(me)

    logger.info("Processing %d cases (concurrency=%d, rpm=%d)", len(entries), concurrency, rpm_limit)

    statuses = await phase3_process_cases(
        run_id, entries, metadata_results,
        rpm_limit=rpm_limit, concurrency=concurrency,
    )

    success = sum(1 for s in statuses.values() if s == "success")
    failed = sum(1 for s in statuses.values() if s != "success")
    logger.info("DONE: %d success, %d failed out of %d", success, failed, len(statuses))
    for cid, status in sorted(statuses.items()):
        if status != "success":
            logger.warning("  FAILED %s: %s", cid[:12], status)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resume Phase 3 from saved batch results")
    parser.add_argument("run_id", help="Batch run directory name")
    parser.add_argument("--rpm-limit", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=1)
    args = parser.parse_args()
    asyncio.run(main(args.run_id, args.rpm_limit, args.concurrency))
