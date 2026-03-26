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
import threading
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

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
from sqlalchemy import text  # noqa: E402


async def _disable_fts_trigger() -> None:
    """Disable the FTS trigger on cases table for faster bulk inserts."""
    async with async_session_factory() as db:
        await db.execute(text(
            "ALTER TABLE cases DISABLE TRIGGER cases_searchable_text_trigger"
        ))
        await db.commit()
    logger.info("FTS trigger DISABLED for bulk ingestion")


async def _enable_fts_trigger() -> None:
    """Re-enable the FTS trigger on cases table."""
    async with async_session_factory() as db:
        await db.execute(text(
            "ALTER TABLE cases ENABLE TRIGGER cases_searchable_text_trigger"
        ))
        await db.commit()
    logger.info("FTS trigger RE-ENABLED")


async def _rebuild_fts_vectors() -> None:
    """Batch-rebuild tsvectors for all cases with NULL searchable_text.

    Much faster than per-row trigger because PostgreSQL processes the UPDATE
    in a single scan rather than invoking the trigger function 35K times.
    """
    logger.info("Rebuilding FTS tsvectors for cases with NULL searchable_text...")
    async with async_session_factory() as db:
        result = await db.execute(text(
            """
            UPDATE cases SET searchable_text =
                setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(citation, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(case_number, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(court, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(judge, ' '), '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(petitioner, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(respondent, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(headnotes, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(outcome_summary, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(description, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(ratio_decidendi, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(operative_order, '')), 'C') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(keywords, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(acts_cited, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(legal_principles_applied, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(array_to_string(issue_classification, ' '), '')), 'D') ||
                setweight(to_tsvector('english', COALESCE(left(full_text, 500000), '')), 'D')
            WHERE searchable_text IS NULL
            """
        ))
        await db.commit()
    logger.info("FTS tsvector rebuild complete — %d rows updated", result.rowcount)


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

async def _validate_api_keys(llm_pool: list) -> list[int]:
    """Validate each API key with a minimal probe call. Returns indices of bad keys."""
    bad_indices = []
    for i, llm in enumerate(llm_pool):
        try:
            await asyncio.wait_for(
                llm.generate("Say OK", max_tokens=5),
                timeout=15.0,
            )
        except Exception as exc:
            logger.error("API key %d is invalid or unreachable: %s", i, exc)
            bad_indices.append(i)
    return bad_indices


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

def _make_shutdown_handler(
    shutdown_event: asyncio.Event,
    loop: asyncio.AbstractEventLoop,
) -> Any:
    """Create a signal handler that safely sets the shutdown event."""

    def _handle_shutdown(sig: int, frame: object) -> None:
        logger.warning(
            "Received signal %s, initiating graceful shutdown...",
            signal.Signals(sig).name,
        )
        if loop.is_running():
            loop.call_soon_threadsafe(shutdown_event.set)
        else:
            shutdown_event.set()

    return _handle_shutdown


# ---------------------------------------------------------------------------
# Progress tracker (SQLite)
# ---------------------------------------------------------------------------


class IngestTracker:
    """SQLite-backed tracker with per-stage progress tracking."""

    def __init__(self, db_path: Path = TRACKER_DB) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        # WAL mode for better concurrent access
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
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
        # Migrate existing DBs that lack warnings column
        try:
            self._conn.execute("ALTER TABLE ingestion_progress ADD COLUMN warnings TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

    def is_processed(self, doc_key: str) -> bool:
        """Check if a document has been fully processed (all stages complete)."""
        with self._lock:
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
        with self._lock:
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

    def add_warning(self, doc_key: str, warning: str) -> None:
        """Append a warning to the doc's warnings field (comma-separated)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT warnings FROM ingestion_progress WHERE doc_key = ?",
                (doc_key,),
            ).fetchone()
            if row and row[0]:
                new_warnings = f"{row[0]},{warning}"
            else:
                new_warnings = warning
            self._conn.execute(
                "UPDATE ingestion_progress SET warnings = ? WHERE doc_key = ?",
                (new_warnings, doc_key),
            )
            self._conn.commit()

    def init_doc(self, doc_key: str, year: int) -> None:
        """Initialize a document entry if it doesn't exist."""
        with self._lock:
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

        with self._lock:
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
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO processed (doc_key, case_id, status) VALUES (?, ?, 'success')",
                (doc_key, case_id),
            )
            self._conn.commit()

    def mark_failed(self, doc_key: str, error: str, *, increment_retry: bool = True) -> None:
        """Record a failure.

        Args:
            doc_key: Document key.
            error: Error message.
            increment_retry: If False, records the error but does NOT increment
                retry_count (used for circuit_breaker_skip / shutdown_skip so
                the case isn't permanently blacklisted).
        """
        with self._lock:
            if increment_retry:
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
            else:
                # Record error without incrementing retry count (transient skip)
                self._conn.execute(
                    "UPDATE ingestion_progress SET last_error = ? WHERE doc_key = ?",
                    (error, doc_key),
                )
                self._conn.execute(
                    "INSERT INTO processed (doc_key, status, error) VALUES (?, 'skipped', ?, 0) "
                    "ON CONFLICT(doc_key) DO UPDATE SET status='skipped', error=?",
                    (doc_key, error, error),
                )
            self._conn.commit()

    def get_failed_at_stage(self, stage: str) -> list[str]:
        """Get doc_keys that failed at a specific stage."""
        with self._lock:
            return [
                row[0] for row in self._conn.execute(
                    f"SELECT doc_key FROM ingestion_progress "
                    f"WHERE stage_{stage} = 0 AND last_error IS NOT NULL",
                ).fetchall()
            ]

    def get_by_quality(self, tier: str) -> list[str]:
        """Get doc_keys with a specific quality tier."""
        with self._lock:
            return [
                row[0] for row in self._conn.execute(
                    "SELECT doc_key FROM ingestion_progress WHERE quality_tier = ?",
                    (tier,),
                ).fetchall()
            ]

    def stats(self) -> dict[str, int]:
        """Overall statistics."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT status, COUNT(*) FROM processed GROUP BY status"
            ).fetchall()
            return {row[0]: row[1] for row in rows}

    def detailed_stats(self, year: int | None = None) -> dict:
        """Detailed stage-level statistics."""
        with self._lock:
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
    """Download a URL to a file with timeout and retry.

    Downloads to a .tmp suffix first, then renames atomically so interrupted
    downloads don't leave partial files that pass the exists() check on resume.
    """
    tmp_dest = dest.with_suffix(dest.suffix + ".tmp")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        with open(tmp_dest, "wb") as f:
            shutil.copyfileobj(resp, f)
    tmp_dest.rename(dest)


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
                timeout=120,
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


def _strip_language_suffix(stem: str) -> str:
    """Strip trailing language suffix (_EN, _HI, etc.) from PDF stem."""
    import re
    return re.sub(r"_[A-Z]{2}$", "", stem)


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

    # O(1) lookup via pre-built index (exact stem or with language suffix stripped)
    if stem_index:
        if pdf_name in stem_index:
            return metadata_map[stem_index[pdf_name]]
        stripped = _strip_language_suffix(pdf_name)
        if stripped != pdf_name and stripped in stem_index:
            return metadata_map[stem_index[stripped]]

    # Substring fallback: check if metadata key appears within the PDF name
    for key, meta in metadata_map.items():
        if str(key) in pdf_name:
            return meta

    # Fallback: return empty dict (LLM will extract everything)
    return {}


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """Circuit breaker with half-open recovery.

    States:
    - CLOSED: normal operation, counts consecutive failures.
    - OPEN: tripped after ``threshold`` failures, rejects immediately.
    - HALF_OPEN: after ``cooldown_secs`` has elapsed since opening, allows
      one probe request. If it succeeds → CLOSED; if it fails → OPEN again.

    All state mutations are guarded by an asyncio.Lock for safety under
    concurrent workers.
    """

    def __init__(self, threshold: int = 10, cooldown_secs: float = 60.0) -> None:
        self._threshold = threshold
        self._cooldown = cooldown_secs
        self._failures = 0
        self._state = "closed"  # closed | open | half_open
        self._opened_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def is_tripped(self) -> bool:
        return self._state == "open"

    async def check(self) -> bool:
        """Return True if the request should proceed, False to reject."""
        async with self._lock:
            if self._state == "closed":
                return True
            if self._state == "open":
                if (time.monotonic() - self._opened_at) >= self._cooldown:
                    self._state = "half_open"
                    logger.info("Circuit breaker entering half-open state (probing)")
                    return True
                return False
            # half_open — only one probe at a time; lock ensures serialisation
            return True

    async def record_success(self) -> None:
        async with self._lock:
            if self._state == "half_open":
                logger.info("Circuit breaker probe succeeded — closing")
            self._failures = 0
            self._state = "closed"

    async def record_failure(self) -> bool:
        """Returns True if the breaker just tripped open."""
        async with self._lock:
            self._failures += 1
            if self._state == "half_open":
                logger.warning("Circuit breaker probe failed — reopening")
                self._state = "open"
                self._opened_at = time.monotonic()
                return True
            if self._failures >= self._threshold:
                self._state = "open"
                self._opened_at = time.monotonic()
                logger.critical(
                    "Circuit breaker OPEN: %d consecutive failures", self._failures
                )
                return True
            return False


# ---------------------------------------------------------------------------
# Core ingestion loop
# ---------------------------------------------------------------------------


async def _reconcile_orphans() -> int:
    """Reset cases stuck in 'processing' from a crashed run."""
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                text(
                    "UPDATE cases SET ingestion_status = 'failed' "
                    "WHERE ingestion_status = 'processing' "
                    "AND updated_at < NOW() - INTERVAL '1 hour' "
                    "RETURNING id"
                )
            )
            orphans = result.fetchall()
            await db.commit()
            if orphans:
                logger.warning("Reset %d orphaned 'processing' cases to 'failed'", len(orphans))
            return len(orphans)
    except Exception as exc:
        logger.warning("Orphan reconciliation failed (non-critical): %s", exc)
        return 0


async def ingest_year(
    year: int,
    data_dir: Path,
    tracker: IngestTracker,
    *,
    limit: int | None = None,
    concurrency: int = 5,
    rpm_limit: int = 30,
    model_override: str | None = None,
    shutdown_event: asyncio.Event | None = None,
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
    if shutdown_event is None:
        shutdown_event = asyncio.Event()

    logger.info("=== Ingesting year %d ===", year)

    # Reconcile orphaned 'processing' rows from previous crashed runs
    await _reconcile_orphans()

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

    # Build per-key rate limiter pools: separate for LLM and embedding
    llm_limiter_pool: RateLimiterPool | None = None
    embed_limiter_pool: RateLimiterPool | None = None
    if rpm_limit > 0:
        llm_limiter_pool = RateLimiterPool(rpm_per_key=rpm_limit)
        embed_limiter_pool = RateLimiterPool(rpm_per_key=rpm_limit * 5)  # Embeddings are cheaper, allow 5x
        logger.info("Rate limiting enabled: LLM %d RPM, Embed %d RPM per key", rpm_limit, rpm_limit * 5)
    else:
        logger.info("Rate limiting disabled (--rpm-limit 0)")

    llm_pool: list[GeminiLLM] = []
    embedder_pool: list[GeminiEmbedder] = []
    for key in api_keys:
        llm_kwargs: dict[str, str] = {"api_key": key}
        if model_override:
            llm_kwargs["model"] = model_override
        else:
            # Hybrid approach: use Flash for Pass 1 ingestion (cheaper, faster)
            llm_kwargs["model"] = settings.gemini_flash_model
        llm_pool.append(GeminiLLM(**llm_kwargs))
        embedder_pool.append(GeminiEmbedder(api_key=key))

    # Validate API keys at startup
    bad_indices = await _validate_api_keys(llm_pool)
    if bad_indices:
        if len(bad_indices) == len(llm_pool):
            logger.error("ALL %d API keys are invalid — aborting", len(llm_pool))
            return {"error": "all_keys_invalid"}
        logger.warning("Removing %d invalid API key(s), continuing with %d", len(bad_indices), len(llm_pool) - len(bad_indices))
        for idx in sorted(bad_indices, reverse=True):
            llm_pool.pop(idx)
            embedder_pool.pop(idx)
            api_keys.pop(idx)

    # Round-robin iterator over (llm, embedder, key) triples
    provider_cycle = itertools.cycle(zip(llm_pool, embedder_pool, api_keys))

    vector_store = get_vector_store()
    graph_store = get_graph_store()
    storage = get_storage()

    # Pre-flight check: verify embedding dimension matches Pinecone index
    try:
        test_embedding = await embedder_pool[0].embed_text("dimension check")
        embed_dim = len(test_embedding)
        pc_stats = await asyncio.to_thread(vector_store._index.describe_index_stats)
        pc_dim = pc_stats.get("dimension", None)
        if pc_dim and embed_dim != pc_dim:
            logger.error(
                "DIMENSION MISMATCH: embedder produces %d-dim vectors but "
                "Pinecone index expects %d-dim — aborting to prevent index corruption",
                embed_dim, pc_dim,
            )
            return {"error": f"dimension_mismatch_{embed_dim}_vs_{pc_dim}"}
        logger.info("Pre-flight OK: embedding dim=%d, Pinecone dim=%s", embed_dim, pc_dim or "empty index")
    except Exception as exc:
        logger.warning("Pre-flight dimension check failed (non-fatal): %s", exc)

    # Apply limit
    pdfs_to_process = pdf_paths[:limit] if limit else pdf_paths

    # Circuit breaker with half-open recovery
    breaker = CircuitBreaker(threshold=10, cooldown_secs=60.0)

    # Progress tracking with ETA
    stats = {"success": 0, "skipped": 0, "failed": 0}
    processed = 0
    total_attempted = 0  # success + failed + skipped for accurate %
    start_time = time.monotonic()

    async def _process_one(
        pdf_path: Path, llm: GeminiLLM, embedder: GeminiEmbedder, api_key: str,
    ) -> None:
        nonlocal processed, total_attempted
        doc_key = f"year={year}/{pdf_path.name}"
        await asyncio.to_thread(tracker.init_doc, doc_key, year)

        # Skip if already processed or permanently failed
        if await asyncio.to_thread(tracker.is_processed, doc_key) or \
           await asyncio.to_thread(tracker.is_permanently_failed, doc_key):
            stats["skipped"] += 1
            total_attempted += 1
            return

        # Get per-key rate limiters (or None if disabled)
        llm_limiter = llm_limiter_pool.get(api_key) if llm_limiter_pool else None
        embed_limiter = embed_limiter_pool.get(api_key) if embed_limiter_pool else None

        try:
            parquet_meta = _match_pdf_to_metadata(pdf_path, metadata_map, stem_index)
            ingestion_warnings: list[str] = []
            async with async_session_factory() as db:
                case_id = await asyncio.wait_for(
                    ingest_judgment(
                        str(pdf_path),
                        parquet_meta,
                        db=db,
                        llm=llm,
                        embedder=embedder,
                        vector_store=vector_store,
                        graph_store=graph_store,
                        storage=storage,
                        llm_rate_limiter=llm_limiter,
                        embed_rate_limiter=embed_limiter,
                        warnings_out=ingestion_warnings,
                    ),
                    timeout=900.0,
                )
            if case_id is None:
                await asyncio.to_thread(tracker.mark_failed, doc_key, "Text extraction failed")
                stats["failed"] += 1
                total_attempted += 1
                await breaker.record_failure()
                return
            await asyncio.to_thread(tracker.mark_success, doc_key, case_id)
            # Mark all stages complete (since ingest_judgment does them all)
            for stage in ("extracted", "metadata", "embedded", "stored", "graphed"):
                await asyncio.to_thread(tracker.mark_stage, doc_key, stage, case_id)
            # Record any warnings (e.g. OCR truncation) for post-run analysis
            for warning in ingestion_warnings:
                await asyncio.to_thread(tracker.add_warning, doc_key, warning)
            stats["success"] += 1
            processed += 1
            total_attempted += 1
            await breaker.record_success()

            # Clean up PDF after successful processing
            try:
                pdf_path.unlink(missing_ok=True)
            except OSError:
                pass

            # Progress logging with ETA (include all attempted for accurate %)
            if processed % 25 == 0 or total_attempted == len(pdfs_to_process):
                elapsed = time.monotonic() - start_time
                rate = processed / max(elapsed / 60, 0.01)  # cases/minute
                remaining = len(pdfs_to_process) - total_attempted
                eta_min = remaining / max(rate, 0.01)
                eta_str = f"{int(eta_min // 60)}h {int(eta_min % 60)}m" if eta_min >= 60 else f"{int(eta_min)}m"
                logger.info(
                    "[%d] %d/%d (%.1f%%) | %.1f cases/min | ETA: %s | %d skipped | %d failed",
                    year, processed, len(pdfs_to_process),
                    total_attempted / max(len(pdfs_to_process), 1) * 100,
                    rate, eta_str, stats["skipped"], stats["failed"],
                )
        except asyncio.TimeoutError:
            logger.error("Timeout after 900s for %s", doc_key)
            await asyncio.to_thread(tracker.mark_failed, doc_key, "timeout_900s", increment_retry=True)
            stats["failed"] += 1
            total_attempted += 1
            await breaker.record_failure()
        except Exception as exc:
            await asyncio.to_thread(tracker.mark_failed, doc_key, str(exc))
            stats["failed"] += 1
            total_attempted += 1
            logger.error("Failed to ingest %s: %s", pdf_path.name, exc)
            await breaker.record_failure()

    # Queue-based workers for bounded concurrency
    queue: asyncio.Queue[tuple[Path, GeminiLLM, GeminiEmbedder, str] | None] = asyncio.Queue()
    for p in pdfs_to_process:
        llm, embedder, api_key = next(provider_cycle)
        await queue.put((p, llm, embedder, api_key))

    # Sentinel values to signal workers to stop
    for _ in range(concurrency):
        await queue.put(None)

    async def _worker(worker_id: int) -> None:
        _breaker_wait_start: float | None = None  # per-worker breaker wait tracker
        _MAX_BREAKER_WAIT = 300.0  # 5 min max wait before giving up
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                break
            # Check shutdown — mark skipped only on intentional shutdown
            if shutdown_event.is_set():
                pdf_path, _llm, _embedder, _api_key = item
                skip_key = f"year={year}/{pdf_path.name}"
                await asyncio.to_thread(
                    tracker.mark_failed, skip_key, "shutdown_skip",
                    increment_retry=False,
                )
                stats["skipped"] += 1
                queue.task_done()
                continue
            # Circuit breaker tripped — wait for cooldown instead of losing items
            if breaker.is_tripped:
                can_proceed = await breaker.check()
                if not can_proceed:
                    # Track how long breaker has been continuously open
                    now = time.monotonic()
                    if _breaker_wait_start is None:
                        _breaker_wait_start = now
                    elif (now - _breaker_wait_start) > _MAX_BREAKER_WAIT:
                        # Breaker open too long — give up on this item
                        pdf_path, _llm, _embedder, _api_key = item
                        skip_key = f"year={year}/{pdf_path.name}"
                        await asyncio.to_thread(
                            tracker.mark_failed, skip_key, "circuit_breaker_timeout",
                            increment_retry=False,
                        )
                        stats["skipped"] += 1
                        queue.task_done()
                        logger.warning("Worker %d: breaker open >5min, skipping %s", worker_id, skip_key)
                        continue
                    # Re-queue the item and wait for cooldown before retrying
                    await queue.put(item)
                    queue.task_done()
                    logger.debug("Worker %d: breaker open, re-queued item, waiting 10s", worker_id)
                    await asyncio.sleep(10.0)
                    continue
                # Breaker recovered — reset wait timer
                _breaker_wait_start = None
            else:
                _breaker_wait_start = None
            try:
                pdf_path, llm, embedder, api_key = item
                await _process_one(pdf_path, llm, embedder, api_key)
            finally:
                queue.task_done()

    workers = []
    for i in range(concurrency):
        workers.append(asyncio.create_task(_worker(i)))

    await asyncio.gather(*workers, return_exceptions=True)

    # Clean up tar and extracted directory after all cases processed
    try:
        tar_path.unlink(missing_ok=True)
    except OSError:
        pass
    if extract_dir.exists():
        shutil.rmtree(extract_dir, ignore_errors=True)

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
    run_parser.add_argument("--concurrency", type=int, default=20, help="Concurrent tasks (default: 20)")
    run_parser.add_argument("--rpm-limit", type=int, default=30, help="Max Gemini LLM API requests per minute per key (0 = no limit)")
    run_parser.add_argument("--data-dir", type=str, default="data", help="Data directory")
    run_parser.add_argument("--model", type=str, default=None, help="Override Gemini model (default: from settings)")
    run_parser.add_argument("--total-limit", type=int, default=None,
                            help="Max total judgments across ALL years (stops when reached)")
    run_parser.add_argument("--disable-fts-trigger", action="store_true",
                            help="Disable FTS trigger during bulk ingestion for 30-40%% faster inserts. Rebuilds tsvectors in batch at the end.")

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

    # Create shutdown event and register signal handlers
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    handler = _make_shutdown_handler(shutdown_event, loop)
    signal.signal(signal.SIGINT, handler)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, handler)

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
        # Process latest years first (most relevant cases first)
        years.reverse()
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

    # Optionally disable FTS trigger for faster bulk inserts
    fts_disabled = getattr(args, "disable_fts_trigger", False)
    if fts_disabled:
        try:
            await _disable_fts_trigger()
        except Exception as exc:
            logger.warning("Could not disable FTS trigger (non-fatal): %s", exc)
            fts_disabled = False

    total_stats: dict[str, int] = {"success": 0, "skipped": 0, "failed": 0}
    total_limit = getattr(args, "total_limit", None)

    for year in years:
        if shutdown_event.is_set():
            logger.warning("Shutdown requested, skipping remaining years.")
            break

        # Compute per-year limit respecting --total-limit
        year_limit = args.limit
        if total_limit is not None:
            remaining = total_limit - total_stats.get("success", 0)
            if remaining <= 0:
                logger.info("Total limit of %d reached — stopping.", total_limit)
                break
            if year_limit is not None:
                year_limit = min(year_limit, remaining)
            else:
                year_limit = remaining

        year_stats = await ingest_year(
            year,
            data_dir,
            tracker,
            limit=year_limit,
            concurrency=args.concurrency,
            rpm_limit=args.rpm_limit,
            model_override=getattr(args, "model", None),
            shutdown_event=shutdown_event,
        )
        for k, v in year_stats.items():
            total_stats[k] = total_stats.get(k, 0) + v

    # Re-enable FTS trigger and batch-rebuild tsvectors
    if fts_disabled:
        try:
            await _rebuild_fts_vectors()
        except Exception as exc:
            logger.error("FTS rebuild failed: %s. Run manually: UPDATE cases SET searchable_text = ... WHERE searchable_text IS NULL", exc)
        try:
            await _enable_fts_trigger()
        except Exception as exc:
            logger.error("Could not re-enable FTS trigger: %s. Run: ALTER TABLE cases ENABLE TRIGGER cases_searchable_text_trigger", exc)

    logger.info("=== INGESTION COMPLETE ===")
    logger.info("Total stats: %s", total_stats)
    logger.info("Tracker stats: %s", tracker.stats())

    # Show detailed report
    for year in years:
        detailed = tracker.detailed_stats(year=year)
        logger.info("Year %d detailed: %s", year, detailed)

    # Clean up external service connections to avoid resource leaks
    try:
        graph = get_graph_store()
        await graph.close()
        logger.info("Neo4j driver closed.")
    except Exception as exc:
        logger.warning("Neo4j cleanup failed (non-fatal): %s", exc)
    try:
        from app.db.postgres import engine as _pg_engine
        await _pg_engine.dispose()
        logger.info("PostgreSQL engine disposed.")
    except Exception as exc:
        logger.warning("PostgreSQL cleanup failed (non-fatal): %s", exc)

    tracker.close()


if __name__ == "__main__":
    asyncio.run(main())
