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
import shutil
import signal
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq
from tenacity import retry, stop_after_attempt, wait_exponential

# Ensure the backend package is importable when running as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import itertools  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.dependencies import (  # noqa: E402
    get_embedder,
    get_graph_store,
    get_llm,
    get_storage,
    get_vector_store,
)
from app.core.ingestion.pipeline import ingest_judgment  # noqa: E402
from app.core.ingestion.rate_limiter import RateLimiterPool  # noqa: E402
from app.core.providers.embeddings.gemini import GeminiEmbedder  # noqa: E402
from app.core.providers.llm.gemini import GeminiLLM  # noqa: E402
from app.db.postgres import async_session_factory  # noqa: E402


def _build_key_pool() -> list[str]:
    """Build a list of Gemini API keys from env (GEMINI_API_KEYS or GEMINI_API_KEY)."""
    import os

    from dotenv import load_dotenv

    # Load .env so GEMINI_API_KEYS is available via os.environ
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    keys_str = os.environ.get("GEMINI_API_KEYS", "")
    if keys_str:
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if keys:
            return keys
    # Fallback to single key from settings
    return [settings.gemini_api_key]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_s3")

S3_BUCKET = "s3://indian-supreme-court-judgments"
TRACKER_DB = Path("data/ingest_tracker.db")

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

shutdown_event = asyncio.Event()


def _handle_shutdown(sig: int, frame: object) -> None:
    """Signal handler for graceful shutdown."""
    logger.warning("Received signal %s, initiating graceful shutdown...", signal.Signals(sig).name)
    shutdown_event.set()


# ---------------------------------------------------------------------------
# Progress tracker (SQLite)
# ---------------------------------------------------------------------------


class IngestTracker:
    """SQLite-backed tracker with per-stage progress tracking."""

    def __init__(self, db_path: Path = TRACKER_DB) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        # WAL mode for better concurrent access
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._migrate_schema()

    def _migrate_schema(self) -> None:
        """Create or migrate the tracking schema."""
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_progress (
                doc_key TEXT PRIMARY KEY,
                case_id TEXT,
                year INTEGER,
                stage_extracted BOOLEAN DEFAULT 0,
                stage_metadata BOOLEAN DEFAULT 0,
                stage_embedded BOOLEAN DEFAULT 0,
                stage_stored BOOLEAN DEFAULT 0,
                stage_graphed BOOLEAN DEFAULT 0,
                text_length INTEGER DEFAULT 0,
                quality_tier TEXT,
                ocr_used BOOLEAN DEFAULT 0,
                chunk_count INTEGER DEFAULT 0,
                last_error TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            )
            """
        )
        # Keep backward compatibility with old 'processed' table
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed (
                doc_key TEXT PRIMARY KEY,
                case_id TEXT,
                status TEXT DEFAULT 'success',
                error TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        self._conn.commit()
        # Migrate existing DBs that lack retry_count column
        try:
            self._conn.execute("ALTER TABLE processed ADD COLUMN retry_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # column already exists

    def is_processed(self, doc_key: str) -> bool:
        """Check if a document has been fully processed (all stages complete)."""
        row = self._conn.execute(
            "SELECT 1 FROM ingestion_progress WHERE doc_key = ? "
            "AND stage_extracted = 1 AND stage_metadata = 1 "
            "AND stage_embedded = 1 AND stage_stored = 1 AND stage_graphed = 1",
            (doc_key,),
        ).fetchone()
        if row:
            return True
        # Backward compat: check old table
        row = self._conn.execute(
            "SELECT 1 FROM processed WHERE doc_key = ? AND status = 'success'",
            (doc_key,),
        ).fetchone()
        return row is not None

    def is_permanently_failed(self, doc_key: str, max_retries: int = 3) -> bool:
        """Check if a document has exceeded the maximum retry count."""
        row = self._conn.execute(
            "SELECT retry_count FROM processed WHERE doc_key = ? AND status = 'failed'",
            (doc_key,),
        ).fetchone()
        if row is not None and row[0] >= max_retries:
            return True
        row = self._conn.execute(
            "SELECT retry_count FROM ingestion_progress WHERE doc_key = ? AND last_error IS NOT NULL",
            (doc_key,),
        ).fetchone()
        return row is not None and row[0] >= max_retries

    def init_doc(self, doc_key: str, year: int) -> None:
        """Initialize a document entry if it doesn't exist."""
        self._conn.execute(
            "INSERT OR IGNORE INTO ingestion_progress (doc_key, year) VALUES (?, ?)",
            (doc_key, year),
        )
        self._conn.commit()

    def mark_stage(self, doc_key: str, stage: str, case_id: str | None = None, **kwargs) -> None:
        """Mark a stage as complete with optional metadata."""
        valid_stages = {"extracted", "metadata", "embedded", "stored", "graphed"}
        if stage not in valid_stages:
            raise ValueError(f"Invalid stage: {stage}. Must be one of {valid_stages}")

        updates = [f"stage_{stage} = 1"]
        params: dict = {}

        if case_id:
            updates.append("case_id = :case_id")
            params["case_id"] = case_id

        for key in ("text_length", "quality_tier", "ocr_used", "chunk_count"):
            if key in kwargs:
                updates.append(f"{key} = :{key}")
                params[key] = kwargs[key]

        # Check if all stages are now complete
        updates_str = ", ".join(updates)
        params["doc_key"] = doc_key

        self._conn.execute(
            f"UPDATE ingestion_progress SET {updates_str} WHERE doc_key = :doc_key",
            params,
        )

        # Check if fully complete and set completed_at
        row = self._conn.execute(
            "SELECT stage_extracted, stage_metadata, stage_embedded, stage_stored, stage_graphed "
            "FROM ingestion_progress WHERE doc_key = ?",
            (doc_key,),
        ).fetchone()
        if row and all(row):
            self._conn.execute(
                "UPDATE ingestion_progress SET completed_at = datetime('now') WHERE doc_key = ?",
                (doc_key,),
            )

        self._conn.commit()

    def mark_success(self, doc_key: str, case_id: str) -> None:
        """Legacy compat: mark as fully successful."""
        self._conn.execute(
            "INSERT OR REPLACE INTO processed (doc_key, case_id, status) VALUES (?, ?, 'success')",
            (doc_key, case_id),
        )
        self._conn.commit()

    def mark_failed(self, doc_key: str, error: str) -> None:
        """Record a failure."""
        self._conn.execute(
            "UPDATE ingestion_progress SET last_error = ?, retry_count = retry_count + 1 "
            "WHERE doc_key = ?",
            (error, doc_key),
        )
        self._conn.execute(
            "INSERT INTO processed (doc_key, status, error, retry_count) VALUES (?, 'failed', ?, 1) "
            "ON CONFLICT(doc_key) DO UPDATE SET status='failed', error=?, retry_count=retry_count+1",
            (doc_key, error, error),
        )
        self._conn.commit()

    def get_failed_at_stage(self, stage: str) -> list[str]:
        """Get doc_keys that failed at a specific stage."""
        return [
            row[0] for row in self._conn.execute(
                f"SELECT doc_key FROM ingestion_progress "
                f"WHERE stage_{stage} = 0 AND last_error IS NOT NULL",
            ).fetchall()
        ]

    def get_by_quality(self, tier: str) -> list[str]:
        """Get doc_keys with a specific quality tier."""
        return [
            row[0] for row in self._conn.execute(
                "SELECT doc_key FROM ingestion_progress WHERE quality_tier = ?",
                (tier,),
            ).fetchall()
        ]

    def stats(self) -> dict[str, int]:
        """Overall statistics."""
        rows = self._conn.execute(
            "SELECT status, COUNT(*) FROM processed GROUP BY status"
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    def detailed_stats(self, year: int | None = None) -> dict:
        """Detailed stage-level statistics."""
        where = "WHERE year = ?" if year else ""
        params = (year,) if year else ()

        total = self._conn.execute(
            f"SELECT COUNT(*) FROM ingestion_progress {where}", params
        ).fetchone()[0]

        stages = {}
        for stage in ("extracted", "metadata", "embedded", "stored", "graphed"):
            count = self._conn.execute(
                f"SELECT COUNT(*) FROM ingestion_progress {where} {'AND' if where else 'WHERE'} stage_{stage} = 1",
                params,
            ).fetchone()[0]
            stages[stage] = count

        quality = {}
        for tier in ("high", "medium", "low"):
            count = self._conn.execute(
                f"SELECT COUNT(*) FROM ingestion_progress {where} {'AND' if where else 'WHERE'} quality_tier = ?",
                params + (tier,),
            ).fetchone()[0]
            quality[tier] = count

        completed = self._conn.execute(
            f"SELECT COUNT(*) FROM ingestion_progress {where} {'AND' if where else 'WHERE'} completed_at IS NOT NULL",
            params,
        ).fetchone()[0]

        failed = self._conn.execute(
            f"SELECT COUNT(*) FROM ingestion_progress {where} {'AND' if where else 'WHERE'} last_error IS NOT NULL",
            params,
        ).fetchone()[0]

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "stages": stages,
            "quality": quality,
        }

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# S3 download helpers
# ---------------------------------------------------------------------------


@retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3), reraise=True)
def _download_with_timeout(url: str, dest: Path, timeout: int = 120) -> None:
    """Download a URL to a file with timeout and retry."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        with open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)


def _s3_download(s3_path: str, local_path: Path) -> bool:
    """Download a file from S3 via HTTPS (public bucket, no auth required).

    Falls back to AWS CLI if available.
    """
    local_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert s3:// URL to HTTPS
    https_url = s3_path.replace(
        "s3://indian-supreme-court-judgments/",
        "https://indian-supreme-court-judgments.s3.amazonaws.com/",
    )

    # Try HTTPS download first (no AWS CLI needed)
    try:
        logger.info("Downloading %s", https_url)
        _download_with_timeout(https_url, local_path)
        logger.info("Downloaded: %s (%.1f MB)", local_path.name, local_path.stat().st_size / 1e6)
        return True
    except (urllib.error.URLError, OSError) as exc:
        logger.warning("HTTPS download failed: %s -- %s", https_url, exc)

    # Fallback to AWS CLI if available
    if shutil.which("aws"):
        try:
            subprocess.run(
                ["aws", "s3", "cp", s3_path, str(local_path), "--no-sign-request"],
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except subprocess.CalledProcessError as exc:
            logger.error("AWS CLI download failed: %s -> %s", s3_path, exc.stderr.strip())

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
                tar.extract(member, path=extract_dir, filter="data")
                pdf_paths.append(extract_dir / member.name)

    logger.info("Extracted %d PDFs from %s", len(pdf_paths), tar_path.name)
    return pdf_paths


def load_parquet_metadata(parquet_path: Path) -> dict[str, dict]:
    """Load Parquet metadata into a dict keyed by the 'path' field.

    Uses pandas to handle schema inconsistencies (mixed types) gracefully.

    Returns:
        Mapping from S3 path (or title-based key) to metadata dict.
    """
    import pandas as pd

    df = pd.read_parquet(parquet_path)
    metadata_map: dict[str, dict] = {}

    for _, pandas_row in df.iterrows():
        row = {col: (val if pd.notna(val) else None) for col, val in pandas_row.items()}
        key = row.get("path") or row.get("title") or str(len(metadata_map))
        metadata_map[str(key)] = row

    logger.info("Loaded %d metadata records from %s", len(metadata_map), parquet_path.name)
    return metadata_map


def _match_pdf_to_metadata(
    pdf_path: Path,
    metadata_map: dict[str, dict],
    stem_index: dict[str, str] | None = None,
) -> dict:
    """Best-effort match a PDF file to its Parquet metadata row.

    Uses a pre-built stem_index for O(1) lookup when available,
    with substring fallback.
    """
    pdf_name = pdf_path.stem

    # O(1) lookup via pre-built index
    if stem_index and pdf_name in stem_index:
        return metadata_map[stem_index[pdf_name]]

    # Try exact path match (substring fallback)
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
    rpm_limit: int = 30,
    model_override: str | None = None,
) -> dict[str, int]:
    """Ingest all judgments for a given year.

    Args:
        year: The year to ingest.
        data_dir: Local directory for downloaded data.
        tracker: Progress tracker for resume support.
        limit: Maximum number of judgments to process (None = all).
        concurrency: Number of concurrent ingestion tasks.
        rpm_limit: Max Gemini API requests per minute per key (0 = no limit).
        model_override: Override Gemini model name (None = use settings default).

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

    # Build stem index for O(1) PDF-to-metadata matching
    stem_index: dict[str, str] = {}
    for key in metadata_map:
        stem = Path(str(key)).stem
        stem_index[stem] = key

    # Initialize providers -- build a pool of LLM+embedder clients for key rotation
    api_keys = _build_key_pool()
    logger.info("Using %d Gemini API key(s) for parallel ingestion", len(api_keys))

    # Build per-key rate limiter pool (0 = disabled)
    rate_limiter_pool: RateLimiterPool | None = None
    if rpm_limit > 0:
        rate_limiter_pool = RateLimiterPool(rpm_per_key=rpm_limit)
        logger.info("Rate limiting enabled: %d RPM per key", rpm_limit)
    else:
        logger.info("Rate limiting disabled (--rpm-limit 0)")

    llm_pool: list[GeminiLLM] = []
    embedder_pool: list[GeminiEmbedder] = []
    for key in api_keys:
        llm_kwargs: dict[str, str] = {"api_key": key}
        if model_override:
            llm_kwargs["model"] = model_override
        llm_pool.append(GeminiLLM(**llm_kwargs))
        embedder_pool.append(GeminiEmbedder(api_key=key))

    # Round-robin iterator over (llm, embedder, key) triples
    provider_cycle = itertools.cycle(zip(llm_pool, embedder_pool, api_keys))

    vector_store = get_vector_store()
    graph_store = get_graph_store()
    storage = get_storage()

    # Apply limit
    pdfs_to_process = pdf_paths[:limit] if limit else pdf_paths

    # Circuit breaker
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 10
    shutdown_flag = False

    # Progress tracking with ETA
    stats = {"success": 0, "skipped": 0, "failed": 0}
    processed = 0
    start_time = time.monotonic()

    async def _process_one(
        pdf_path: Path, llm: GeminiLLM, embedder: GeminiEmbedder, api_key: str,
    ) -> None:
        nonlocal processed, consecutive_failures, shutdown_flag
        doc_key = f"year={year}/{pdf_path.name}"
        tracker.init_doc(doc_key, year)

        # Skip if already processed or permanently failed
        if tracker.is_processed(doc_key) or tracker.is_permanently_failed(doc_key):
            stats["skipped"] += 1
            return

        # Get the per-key rate limiter (or None if disabled)
        limiter = rate_limiter_pool.get(api_key) if rate_limiter_pool else None

        try:
            parquet_meta = _match_pdf_to_metadata(pdf_path, metadata_map, stem_index)
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
                    rate_limiter=limiter,
                )
            tracker.mark_success(doc_key, case_id)
            # Mark all stages complete (since ingest_judgment does them all)
            tracker.mark_stage(doc_key, "extracted", case_id=case_id)
            tracker.mark_stage(doc_key, "metadata", case_id=case_id)
            tracker.mark_stage(doc_key, "embedded", case_id=case_id)
            tracker.mark_stage(doc_key, "stored", case_id=case_id)
            tracker.mark_stage(doc_key, "graphed", case_id=case_id)
            stats["success"] += 1
            processed += 1
            consecutive_failures = 0

            # Progress logging with ETA
            if processed % 25 == 0 or processed == len(pdfs_to_process):
                elapsed = time.monotonic() - start_time
                rate = processed / max(elapsed / 60, 0.01)  # cases/minute
                remaining = len(pdfs_to_process) - processed - stats["skipped"]
                eta_min = remaining / max(rate, 0.01)
                eta_str = f"{int(eta_min // 60)}h {int(eta_min % 60)}m" if eta_min >= 60 else f"{int(eta_min)}m"
                logger.info(
                    "[%d] %d/%d (%.1f%%) | %.1f cases/min | ETA: %s | %d failed",
                    year, processed, len(pdfs_to_process),
                    processed / max(len(pdfs_to_process), 1) * 100,
                    rate, eta_str, stats["failed"],
                )
        except Exception as exc:
            tracker.mark_failed(doc_key, str(exc))
            stats["failed"] += 1
            consecutive_failures += 1
            logger.error("Failed to ingest %s: %s", pdf_path.name, exc)

            # Circuit breaker check
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.critical("Circuit breaker: %d consecutive failures. Stopping.", MAX_CONSECUTIVE_FAILURES)
                shutdown_flag = True

    # Queue-based workers for bounded concurrency
    queue: asyncio.Queue[tuple[Path, GeminiLLM, GeminiEmbedder, str] | None] = asyncio.Queue()
    for p in pdfs_to_process:
        llm, embedder, api_key = next(provider_cycle)
        await queue.put((p, llm, embedder, api_key))

    # Sentinel values to signal workers to stop
    for _ in range(concurrency):
        await queue.put(None)

    async def _worker(worker_id: int) -> None:
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                break
            # Check shutdown signals before processing
            if shutdown_event.is_set() or shutdown_flag:
                queue.task_done()
                continue
            try:
                pdf_path, llm, embedder, api_key = item
                await _process_one(pdf_path, llm, embedder, api_key)
            finally:
                queue.task_done()

    workers = []
    for i in range(concurrency):
        workers.append(asyncio.create_task(_worker(i)))

    await asyncio.gather(*workers, return_exceptions=True)

    logger.info("Year %d complete: %s", year, stats)
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bulk ingest Indian Supreme Court judgments from AWS Open Data"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- run command (default behavior) ---
    run_parser = subparsers.add_parser("run", help="Run full ingestion pipeline")
    run_parser.add_argument("--year", type=int, help="Ingest a single year")
    run_parser.add_argument("--year-from", type=int, help="Start year (inclusive)")
    run_parser.add_argument("--year-to", type=int, help="End year (inclusive)")
    run_parser.add_argument("--resume", action="store_true", help="Resume interrupted run")
    run_parser.add_argument("--limit", type=int, default=None, help="Max judgments per year")
    run_parser.add_argument("--concurrency", type=int, default=5, help="Concurrent tasks")
    run_parser.add_argument("--rpm-limit", type=int, default=30, help="Max Gemini API requests per minute per key (0 = no limit)")
    run_parser.add_argument("--data-dir", type=str, default="data", help="Data directory")
    run_parser.add_argument("--model", type=str, default=None, help="Override Gemini model (default: from settings)")

    # --- report command ---
    report_parser = subparsers.add_parser("report", help="Show ingestion quality report")
    report_parser.add_argument("--year", type=int, help="Filter by year")

    # --- retry command ---
    retry_parser = subparsers.add_parser("retry", help="Retry failed items at a specific stage")
    retry_parser.add_argument("--stage", required=True, choices=["extracted", "metadata", "embedded", "stored", "graphed"])
    retry_parser.add_argument("--quality-tier", choices=["high", "medium", "low"])
    retry_parser.add_argument("--concurrency", type=int, default=5)
    retry_parser.add_argument("--data-dir", type=str, default="data")

    # Backward compat: if no subcommand, treat args as "run"
    args = parser.parse_args()
    if args.command is None:
        # Legacy mode: parse as run command
        args = run_parser.parse_args()
        args.command = "run"

    return args


async def main() -> None:
    args = parse_args()

    # Register graceful shutdown handlers
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    tracker = IngestTracker()

    if args.command == "report":
        stats = tracker.detailed_stats(year=args.year)
        year_label = f"Year {args.year}" if args.year else "All years"
        print(f"\n=== Ingestion Report: {year_label} ===")
        print(f"Total documents: {stats['total']}")
        print(f"Completed:       {stats['completed']}")
        print(f"Failed:          {stats['failed']}")
        print(f"\nStage completion:")
        for stage, count in stats["stages"].items():
            pct = (count / stats["total"] * 100) if stats["total"] else 0
            print(f"  {stage:12s}: {count:5d} ({pct:.1f}%)")
        print(f"\nQuality distribution:")
        for tier, count in stats["quality"].items():
            pct = (count / stats["total"] * 100) if stats["total"] else 0
            print(f"  {tier:12s}: {count:5d} ({pct:.1f}%)")
        print()
        tracker.close()
        return

    if args.command == "retry":
        doc_keys = tracker.get_failed_at_stage(args.stage)
        if args.quality_tier:
            quality_keys = set(tracker.get_by_quality(args.quality_tier))
            doc_keys = [k for k in doc_keys if k in quality_keys]
        logger.info("Found %d documents to retry at stage '%s'", len(doc_keys), args.stage)
        # TODO: implement per-stage retry (requires stage-specific processing functions)
        logger.info("Per-stage retry not yet implemented. Use 'run --resume' for now.")
        tracker.close()
        return

    # Default: run command
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    years: list[int] = []
    if args.year:
        years = [args.year]
    elif args.year_from and args.year_to:
        years = list(range(args.year_from, args.year_to + 1))
    elif args.resume:
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
        if shutdown_event.is_set():
            logger.warning("Shutdown requested, skipping remaining years.")
            break

        year_stats = await ingest_year(
            year,
            data_dir,
            tracker,
            limit=args.limit,
            concurrency=args.concurrency,
            rpm_limit=args.rpm_limit,
            model_override=getattr(args, "model", None),
        )
        for k, v in year_stats.items():
            total_stats[k] = total_stats.get(k, 0) + v

    logger.info("=== INGESTION COMPLETE ===")
    logger.info("Total stats: %s", total_stats)
    logger.info("Tracker stats: %s", tracker.stats())

    # Show detailed report
    for year in years:
        detailed = tracker.detailed_stats(year=year)
        logger.info("Year %d detailed: %s", year, detailed)

    tracker.close()


if __name__ == "__main__":
    asyncio.run(main())
