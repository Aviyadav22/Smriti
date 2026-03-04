"""Bulk ingestion script for Indian Supreme Court judgments from AWS Open Data.

Downloads tar/parquet files from s3://indian-supreme-court-judgments/ and
runs the ingestion pipeline for each judgment.

Usage:
    python scripts/ingest_s3.py --year 2024
    python scripts/ingest_s3.py --year-from 2020 --year-to 2024
    python scripts/ingest_s3.py --resume
    python scripts/ingest_s3.py --year 2024 --limit 100
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

# Ensure the backend package is importable when running as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.dependencies import (  # noqa: E402
    get_embedder,
    get_graph_store,
    get_llm,
    get_storage,
    get_vector_store,
)
from app.core.ingestion.pipeline import ingest_judgment  # noqa: E402
from app.db.postgres import async_session_factory  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_s3")

S3_BUCKET = "s3://indian-supreme-court-judgments"
TRACKER_DB = Path("data/ingest_tracker.db")


# ---------------------------------------------------------------------------
# Progress tracker (SQLite)
# ---------------------------------------------------------------------------


class IngestTracker:
    """SQLite-backed tracker for resume support."""

    def __init__(self, db_path: Path = TRACKER_DB) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed (
                doc_key TEXT PRIMARY KEY,
                case_id TEXT,
                status TEXT DEFAULT 'success',
                error TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        self._conn.commit()

    def is_processed(self, doc_key: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM processed WHERE doc_key = ? AND status = 'success'",
            (doc_key,),
        ).fetchone()
        return row is not None

    def mark_success(self, doc_key: str, case_id: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO processed (doc_key, case_id, status) VALUES (?, ?, 'success')",
            (doc_key, case_id),
        )
        self._conn.commit()

    def mark_failed(self, doc_key: str, error: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO processed (doc_key, status, error) VALUES (?, 'failed', ?)",
            (doc_key, error),
        )
        self._conn.commit()

    def stats(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT status, COUNT(*) FROM processed GROUP BY status"
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# S3 download helpers
# ---------------------------------------------------------------------------


def _s3_download(s3_path: str, local_path: Path) -> bool:
    """Download a file from S3 using the AWS CLI (no auth required)."""
    local_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["aws", "s3", "cp", s3_path, str(local_path), "--no-sign-request"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("S3 download failed: %s → %s", s3_path, exc.stderr.strip())
        return False


def download_year_data(year: int, data_dir: Path) -> tuple[Path | None, Path | None]:
    """Download the English tar and Parquet metadata for a given year.

    Returns:
        Tuple of (tar_path, parquet_path). Either may be None on failure.
    """
    tar_s3 = f"{S3_BUCKET}/data/tar/year={year}/english/english.tar"
    parquet_s3 = f"{S3_BUCKET}/metadata/parquet/year={year}/metadata.parquet"

    tar_local = data_dir / f"year={year}" / "english.tar"
    parquet_local = data_dir / f"year={year}" / "metadata.parquet"

    tar_ok = tar_local.exists() or _s3_download(tar_s3, tar_local)
    pq_ok = parquet_local.exists() or _s3_download(parquet_s3, parquet_local)

    return (tar_local if tar_ok else None, parquet_local if pq_ok else None)


def extract_tar(tar_path: Path, extract_dir: Path) -> list[Path]:
    """Extract PDFs from a tar archive."""
    extract_dir.mkdir(parents=True, exist_ok=True)
    pdf_paths: list[Path] = []

    with tarfile.open(tar_path, "r") as tar:
        for member in tar.getmembers():
            if member.name.endswith(".pdf"):
                tar.extract(member, path=extract_dir)
                pdf_paths.append(extract_dir / member.name)

    logger.info("Extracted %d PDFs from %s", len(pdf_paths), tar_path.name)
    return pdf_paths


def load_parquet_metadata(parquet_path: Path) -> dict[str, dict]:
    """Load Parquet metadata into a dict keyed by the 'path' field.

    Returns:
        Mapping from S3 path (or title-based key) to metadata dict.
    """
    table = pq.read_table(parquet_path)
    df = table.to_pydict()
    num_rows = len(df.get("title", []))

    metadata_map: dict[str, dict] = {}
    for i in range(num_rows):
        row = {col: df[col][i] for col in df}
        key = row.get("path") or row.get("title") or str(i)
        metadata_map[str(key)] = row

    logger.info("Loaded %d metadata records from %s", len(metadata_map), parquet_path.name)
    return metadata_map


def _match_pdf_to_metadata(
    pdf_path: Path,
    metadata_map: dict[str, dict],
) -> dict:
    """Best-effort match a PDF file to its Parquet metadata row."""
    pdf_name = pdf_path.stem

    # Try exact path match
    for key, meta in metadata_map.items():
        if pdf_name in str(key):
            return meta

    # Fallback: return empty dict (LLM will extract everything)
    return {}


# ---------------------------------------------------------------------------
# Core ingestion loop
# ---------------------------------------------------------------------------


async def ingest_year(
    year: int,
    data_dir: Path,
    tracker: IngestTracker,
    *,
    limit: int | None = None,
    concurrency: int = 5,
) -> dict[str, int]:
    """Ingest all judgments for a given year.

    Args:
        year: The year to ingest.
        data_dir: Local directory for downloaded data.
        tracker: Progress tracker for resume support.
        limit: Maximum number of judgments to process (None = all).
        concurrency: Number of concurrent ingestion tasks.

    Returns:
        Stats dict with success/failure counts.
    """
    logger.info("=== Ingesting year %d ===", year)

    # Download data
    tar_path, parquet_path = download_year_data(year, data_dir)
    if tar_path is None:
        logger.error("Failed to download tar for year %d", year)
        return {"error": 1}

    # Extract PDFs
    extract_dir = data_dir / f"year={year}" / "extracted"
    pdf_paths = extract_tar(tar_path, extract_dir)

    # Load metadata
    metadata_map: dict[str, dict] = {}
    if parquet_path and parquet_path.exists():
        metadata_map = load_parquet_metadata(parquet_path)

    # Initialize providers
    llm = get_llm()
    embedder = get_embedder()
    vector_store = get_vector_store()
    graph_store = get_graph_store()
    storage = get_storage()

    # Process PDFs with bounded concurrency
    semaphore = asyncio.Semaphore(concurrency)
    stats = {"success": 0, "skipped": 0, "failed": 0}
    processed = 0

    async def _process_one(pdf_path: Path) -> None:
        nonlocal processed
        doc_key = f"year={year}/{pdf_path.name}"

        if tracker.is_processed(doc_key):
            stats["skipped"] += 1
            return

        async with semaphore:
            try:
                parquet_meta = _match_pdf_to_metadata(pdf_path, metadata_map)
                async with async_session_factory() as db:
                    case_id = await ingest_judgment(
                        str(pdf_path),
                        parquet_meta,
                        db=db,
                        llm=llm,
                        embedder=embedder,
                        vector_store=vector_store,
                        graph_store=graph_store,
                        storage=storage,
                    )
                tracker.mark_success(doc_key, case_id)
                stats["success"] += 1
                processed += 1
                if processed % 50 == 0:
                    logger.info("Progress: %d/%d processed", processed, len(pdf_paths))
            except Exception as exc:
                tracker.mark_failed(doc_key, str(exc))
                stats["failed"] += 1
                logger.error("Failed to ingest %s: %s", pdf_path.name, exc)

    # Apply limit
    pdfs_to_process = pdf_paths[:limit] if limit else pdf_paths

    # Run concurrently
    tasks = [_process_one(p) for p in pdfs_to_process]
    await asyncio.gather(*tasks)

    logger.info("Year %d complete: %s", year, stats)
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bulk ingest Indian Supreme Court judgments from AWS Open Data"
    )
    parser.add_argument("--year", type=int, help="Ingest a single year")
    parser.add_argument("--year-from", type=int, help="Start year (inclusive)")
    parser.add_argument("--year-to", type=int, help="End year (inclusive)")
    parser.add_argument("--resume", action="store_true", help="Resume interrupted run")
    parser.add_argument(
        "--limit", type=int, default=None, help="Max judgments per year"
    )
    parser.add_argument(
        "--concurrency", type=int, default=5, help="Concurrent ingestion tasks"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Local directory for downloaded data",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    tracker = IngestTracker()

    # Determine years to process
    years: list[int] = []
    if args.year:
        years = [args.year]
    elif args.year_from and args.year_to:
        years = list(range(args.year_from, args.year_to + 1))
    elif args.resume:
        # Resume: re-process all years that have partial data
        existing = sorted(
            int(d.name.replace("year=", ""))
            for d in data_dir.iterdir()
            if d.is_dir() and d.name.startswith("year=")
        )
        years = existing if existing else []
        logger.info("Resuming for years: %s", years)
    else:
        logger.error("Specify --year, --year-from/--year-to, or --resume")
        sys.exit(1)

    total_stats: dict[str, int] = {"success": 0, "skipped": 0, "failed": 0}

    for year in years:
        year_stats = await ingest_year(
            year,
            data_dir,
            tracker,
            limit=args.limit,
            concurrency=args.concurrency,
        )
        for k, v in year_stats.items():
            total_stats[k] = total_stats.get(k, 0) + v

    logger.info("=== INGESTION COMPLETE ===")
    logger.info("Total stats: %s", total_stats)
    logger.info("Tracker stats: %s", tracker.stats())
    tracker.close()


if __name__ == "__main__":
    asyncio.run(main())
