"""Vertex AI batch ingestion pipeline for Indian Supreme Court judgments.

Uses Vertex AI batch API for metadata extraction (50% cheaper than online),
then processes cases online for chunking, embedding, and vector upsert.

4-Phase pipeline:
  Phase 1: Text extraction + GCS upload
  Phase 2: Batch metadata extraction via Vertex AI
  Phase 3: Online processing per case (chunk, embed, store, graph)
  Phase 4: Quality check

Usage:
    python scripts/batch_ingest_vertex.py --year 2024
    python scripts/batch_ingest_vertex.py --all --limit 500
    python scripts/batch_ingest_vertex.py --resume batch_2026-03-28_2024
    python scripts/batch_ingest_vertex.py --quality-check batch_2026-03-28_2024
    python scripts/batch_ingest_vertex.py --year 2024 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import logging
import os
import random
import signal
import sys
import time
import uuid
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure the backend package is importable when running as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import google.auth  # noqa: E402
import httpx  # noqa: E402
from google.api_core import exceptions as gapi_exceptions  # noqa: E402
from google.cloud import storage as gcs_storage  # noqa: E402
from google.genai import errors as genai_errors  # noqa: E402
from google.oauth2 import service_account as gcp_service_account  # noqa: E402
from sqlalchemy import text as sa_text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.ingestion.anonymizer import anonymize_text, detect_sensitive_case  # noqa: E402
from app.core.ingestion.chunker import (  # noqa: E402
    chunk_judgment,
    detect_judgment_sections,
)
from app.core.ingestion.contextual_embeddings import batch_contextualize_chunks  # noqa: E402
from app.core.ingestion.metadata import (  # noqa: E402
    CaseMetadata,
    compute_extraction_confidence,
    cross_validate_propositions,
    merge_metadata,
    validate_cross_fields,
    validate_parquet_data,
    validate_with_regex,
    _parse_judge_names,
)
from app.core.ingestion.pdf import extract_and_score  # noqa: E402
from app.core.ingestion.pipeline import (  # noqa: E402
    _build_citation_graph,
    _compute_text_hash,
    _embed_chunks,
    _extract_citation_equivalents,
    _insert_case,
    _link_citation_equivalents,
    _persist_citation_equivalents,
    _persist_sections,
    _persist_statute_interpretations,
    _upsert_proposition_vectors,
    _upsert_vectors,
)
from app.core.ingestion.rate_limiter import AsyncRateLimiter  # noqa: E402
from app.core.ingestion.section_summarizer import (  # noqa: E402
    build_pinecone_summary_vectors,
    generate_section_summaries,
)
from app.core.legal.extractor import (  # noqa: E402
    extract_acts_cited,
    extract_citations,
    normalize_acts_cited_list,
)
from app.core.legal.prompts import (  # noqa: E402
    METADATA_EXTRACTION_SYSTEM,
    METADATA_EXTRACTION_USER,
    METADATA_OUTPUT_SCHEMA,
)
from app.core.legal.statute_enrichment import enrich_statute_cross_references  # noqa: E402
from app.db.postgres import async_session_factory  # noqa: E402
from scripts.ingest_s3 import (  # noqa: E402
    _disable_fts_trigger,
    _enable_fts_trigger,
    _match_pdf_to_metadata,
    _rebuild_fts_vectors,
    download_year_data,
    extract_tar,
    load_parquet_metadata,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GCS_BUCKET = os.environ.get("GCS_BUCKET", "smriti-batch-ingestion")
BATCH_MODEL = "gemini-2.5-flash"
DATA_DIR = Path("data")
BATCH_RUNS_DIR = DATA_DIR / "batch_runs"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_LOG_FILE = DATA_DIR / "batch_ingest.log"
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


class _FlushFileHandler(logging.FileHandler):
    """FileHandler that flushes after every emit."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


_file_handler = _FlushFileHandler(str(_LOG_FILE), mode="a", encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
_console_handler = logging.StreamHandler(sys.stderr)
_console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logging.root.addHandler(_file_handler)
logging.root.addHandler(_console_handler)
logging.root.setLevel(logging.INFO)
logger = logging.getLogger("batch_ingest_vertex")


def _get_gcs_client() -> gcs_storage.Client:
    """Create a GCS client using service account credentials from GOOGLE_APPLICATION_CREDENTIALS."""
    import os

    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path and Path(creds_path).exists():
        credentials = gcp_service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return gcs_storage.Client(
            project=settings.gemini_vertexai_project,
            credentials=credentials,
        )
    # Fallback to ADC
    return gcs_storage.Client(project=settings.gemini_vertexai_project)

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

_shutdown_event: asyncio.Event | None = None


def _init_shutdown_event() -> asyncio.Event:
    """Create the shutdown event inside the running event loop."""
    global _shutdown_event
    _shutdown_event = asyncio.Event()
    return _shutdown_event


def _make_shutdown_handler(loop: asyncio.AbstractEventLoop) -> Any:
    """Create a signal handler that safely sets the shutdown event."""

    def _handle(sig: int, frame: object) -> None:
        logger.warning(
            "Received signal %s — initiating graceful shutdown...",
            signal.Signals(sig).name,
        )
        if _shutdown_event is None:
            return
        if loop.is_running():
            loop.call_soon_threadsafe(_shutdown_event.set)
        else:
            _shutdown_event.set()

    return _handle


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ManifestEntry:
    """A single case in the batch manifest."""

    case_id: str
    pdf_local_path: str
    gcs_pdf_uri: str
    text_hash: str
    full_text: str
    parquet_meta: dict[str, Any]
    quality_tier: str
    page_count: int
    page_map: list[dict[str, Any]]
    char_count: int


# ---------------------------------------------------------------------------
# Phase 1: Text Extraction + GCS Upload
# ---------------------------------------------------------------------------


async def phase1_extract_and_upload(
    year: int,
    limit: int,
    dry_run: bool = False,
) -> tuple[str, list[ManifestEntry]]:
    """Download S3 data, extract text, dedup, upload PDFs to GCS.

    Returns (run_id, manifest_entries).
    """
    run_id = f"batch_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_{year}"
    run_dir = BATCH_RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== PHASE 1: Text Extraction + GCS Upload (year=%d) ===", year)

    # Download year data from S3
    s3_data_dir = DATA_DIR / "s3_cache"
    s3_data_dir.mkdir(parents=True, exist_ok=True)
    tar_path, parquet_path = download_year_data(year, s3_data_dir)

    if not tar_path or not parquet_path:
        logger.error("Failed to download data for year %d", year)
        return run_id, []

    # Extract PDFs
    extract_dir = s3_data_dir / f"year={year}" / "pdfs"
    pdf_paths = extract_tar(tar_path, extract_dir)
    logger.info("Extracted %d PDFs for year %d", len(pdf_paths), year)

    # Load parquet metadata
    metadata_map = load_parquet_metadata(parquet_path)

    # Build stem index for O(1) lookup
    stem_index: dict[str, str] = {}
    for key in metadata_map:
        stem = Path(str(key)).stem
        stem_index[stem] = key

    # GCS client initialization skipped — per-PDF uploads removed to prevent OOM.
    # PDFs will be bulk-uploaded to GCS separately after ingestion.

    manifest: list[ManifestEntry] = []
    skipped_dedup = 0
    skipped_extraction = 0

    for i, pdf_path in enumerate(pdf_paths):
        if len(manifest) >= limit:
            break

        if _shutdown_event.is_set():
            logger.warning("Shutdown requested during Phase 1, stopping extraction")
            break

        # Extract text
        logger.info("[%d/%d] Extracting text from %s", i + 1, len(pdf_paths), pdf_path.name)

        # Skip oversized PDFs that cause OOM (>250 pages)
        try:
            import fitz
            with fitz.open(str(pdf_path)) as doc:
                if doc.page_count > 250:
                    logger.warning(
                        "Skipping oversized PDF %s (%d pages) to prevent OOM",
                        pdf_path.name, doc.page_count,
                    )
                    skipped_extraction += 1
                    continue
        except Exception:
            pass  # If page count check fails, try extraction anyway

        try:
            quality = await extract_and_score(str(pdf_path))
        except (OSError, RuntimeError, MemoryError) as exc:
            logger.warning("Text extraction failed for %s: %s", pdf_path.name, exc)
            skipped_extraction += 1
            continue

        if not quality.text or quality.char_count < 50:
            logger.warning("Insufficient text from %s (%d chars)", pdf_path.name, quality.char_count)
            skipped_extraction += 1
            continue

        # Anonymize PII
        full_text, _pii_masked = anonymize_text(quality.text)

        # Dedup via text_hash (skip only if fully ingested with chunk_count > 0)
        text_hash = _compute_text_hash(full_text)
        async with async_session_factory() as db:
            existing = await db.execute(
                sa_text("SELECT id, chunk_count FROM cases WHERE text_hash = :hash"),
                {"hash": text_hash},
            )
            row = existing.fetchone()
            if row and row[1] and row[1] > 0:
                skipped_dedup += 1
                continue

        # Match to parquet metadata
        parquet_meta = _match_pdf_to_metadata(pdf_path, metadata_map, stem_index)

        # Generate case ID
        case_id = str(uuid.uuid4())

        # Skip per-PDF GCS upload during Phase 1 to prevent OOM on large batches.
        # PDFs will be bulk-uploaded to GCS separately after ingestion.
        # Phase 2 batch only needs the text (embedded in JSONL), not the PDF.
        gcs_uri = f"local://{pdf_path}"

        logger.info(
            "[%d/%d] %s: %d chars, tier=%s, gcs=%s",
            i + 1, len(pdf_paths), pdf_path.name, quality.char_count, quality.tier,
            "ok" if gcs_uri.startswith("gs://") else "local",
        )
        entry = ManifestEntry(
            case_id=case_id,
            pdf_local_path=str(pdf_path),
            gcs_pdf_uri=gcs_uri,
            text_hash=text_hash,
            full_text=full_text,
            parquet_meta=parquet_meta,
            quality_tier=quality.tier,
            page_count=quality.page_count,
            page_map=quality.page_map,
            char_count=quality.char_count,
        )
        manifest.append(entry)

        if (i + 1) % 10 == 0:
            logger.info(
                "Phase 1 progress: %d/%d PDFs processed, %d in manifest, %d dedup skipped",
                i + 1, len(pdf_paths), len(manifest), skipped_dedup,
            )

    # Save manifest
    manifest_data = [
        {
            "case_id": e.case_id,
            "pdf_local_path": e.pdf_local_path,
            "gcs_pdf_uri": e.gcs_pdf_uri,
            "text_hash": e.text_hash,
            "quality_tier": e.quality_tier,
            "page_count": e.page_count,
            "page_map": e.page_map,
            "char_count": e.char_count,
            "parquet_meta": {
                k: (str(v) if v is not None and not isinstance(v, (str, int, float, bool, list)) else v)
                for k, v in e.parquet_meta.items()
            },
        }
        for e in manifest
    ]
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2, default=str), encoding="utf-8")

    # Save full texts separately (too large for manifest JSON)
    texts_dir = run_dir / "texts"
    texts_dir.mkdir(exist_ok=True)
    for entry in manifest:
        text_path = texts_dir / f"{entry.case_id}.txt"
        text_path.write_text(entry.full_text, encoding="utf-8")

    logger.info(
        "Phase 1 complete: %d cases in manifest, %d dedup skipped, %d extraction failures",
        len(manifest), skipped_dedup, skipped_extraction,
    )
    return run_id, manifest


# ---------------------------------------------------------------------------
# Phase 2: Batch Metadata Extraction via Vertex AI
# ---------------------------------------------------------------------------


def _build_batch_jsonl_entry(case_id: str, gcs_pdf_uri: str, full_text: str) -> dict:
    """Build a single JSONL entry for the Vertex AI batch request.

    Uses PDF multimodal when GCS URI is available, falls back to text.
    """
    # For text fallback, use head+tail truncation (same as online pipeline)
    if gcs_pdf_uri.startswith("gs://"):
        truncated_text = "[See attached PDF document]"
    else:
        _HEAD_CHARS, _TAIL_CHARS = 30_000, 20_000
        if len(full_text) > _HEAD_CHARS + _TAIL_CHARS:
            truncated_text = (
                full_text[:_HEAD_CHARS]
                + "\n\n[...middle section truncated for length...]\n\n"
                + full_text[-_TAIL_CHARS:]
            )
        else:
            truncated_text = full_text
    user_prompt = METADATA_EXTRACTION_USER.format(judgment_text=truncated_text)

    contents: list[dict[str, Any]] = []
    if gcs_pdf_uri.startswith("gs://"):
        contents.append({
            "role": "user",
            "parts": [
                {"fileData": {"fileUri": gcs_pdf_uri, "mimeType": "application/pdf"}},
                {"text": user_prompt},
            ],
        })
    else:
        contents.append({
            "role": "user",
            "parts": [{"text": user_prompt}],
        })

    return {
        "custom_id": case_id,
        "request": {
            "model": f"publishers/google/models/{BATCH_MODEL}",
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": METADATA_EXTRACTION_SYSTEM}],
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": METADATA_OUTPUT_SCHEMA,
                "temperature": 0.1,
                "maxOutputTokens": 16384,
            },
        },
    }


async def phase2_batch_metadata(
    run_id: str,
    manifest: list[ManifestEntry],
) -> dict[str, dict]:
    """Submit batch metadata extraction job to Vertex AI and poll for results.

    Returns a dict of case_id -> raw LLM result dict.
    """
    run_dir = BATCH_RUNS_DIR / run_id
    logger.info("=== PHASE 2: Batch Metadata Extraction (%d cases) ===", len(manifest))

    if not manifest:
        logger.warning("No cases to process in Phase 2")
        return {}

    # Build JSONL
    jsonl_lines: list[str] = []
    case_id_order: list[str] = []
    for entry in manifest:
        line = _build_batch_jsonl_entry(entry.case_id, entry.gcs_pdf_uri, entry.full_text)
        jsonl_lines.append(json.dumps(line))
        case_id_order.append(entry.case_id)

    # Save JSONL locally
    jsonl_path = run_dir / "batch_requests.jsonl"
    jsonl_path.write_text("\n".join(jsonl_lines), encoding="utf-8")

    # Upload JSONL to GCS
    gcs_client = _get_gcs_client()
    bucket = gcs_client.bucket(GCS_BUCKET)
    jsonl_blob = bucket.blob(f"batch_jobs/{run_id}/requests.jsonl")
    jsonl_blob.upload_from_filename(str(jsonl_path))
    gcs_input_uri = f"gs://{GCS_BUCKET}/batch_jobs/{run_id}/requests.jsonl"
    gcs_output_uri = f"gs://{GCS_BUCKET}/batch_jobs/{run_id}/results/"

    logger.info("Uploaded JSONL to %s (%d requests)", gcs_input_uri, len(jsonl_lines))

    # Submit batch job via google.genai SDK
    from google import genai  # noqa: E402

    client = genai.Client(
        vertexai=True,
        project=settings.gemini_vertexai_project,
        location=settings.gemini_vertexai_location,
    )

    batch_job = client.batches.create(
        model=BATCH_MODEL,
        src=gcs_input_uri,
        config={
            "display_name": f"smriti-metadata-{run_id}",
            "dest": gcs_output_uri,
        },
    )
    logger.info("Batch job submitted: %s", batch_job.name)

    # Save batch job name for resume
    (run_dir / "batch_job_name.txt").write_text(batch_job.name, encoding="utf-8")

    # Poll until complete
    poll_interval = 120  # 2 minutes
    while True:
        if _shutdown_event.is_set():
            logger.warning("Shutdown requested during Phase 2 polling")
            raise KeyboardInterrupt("Shutdown during batch polling")

        batch_job = client.batches.get(name=batch_job.name)
        state = batch_job.state
        logger.info("Batch job state: %s", state)

        if state == "JOB_STATE_SUCCEEDED":
            break
        elif state in ("JOB_STATE_FAILED", "JOB_STATE_CANCELLED"):
            logger.error("Batch job failed with state: %s", state)
            raise RuntimeError(f"Batch job failed: {state}")

        await asyncio.sleep(poll_interval)

    # Download results
    results: dict[str, dict] = {}
    failures = 0

    # Build a set of valid case IDs for custom_id validation
    valid_case_ids = {e.case_id for e in manifest}

    result_blobs = list(bucket.list_blobs(prefix=f"batch_jobs/{run_id}/results/"))
    global_line = 0  # Global counter across ALL result files — never resets
    missing_custom_id_count = 0  # Track missing custom_ids for safety halt
    for blob in result_blobs:
        if not blob.name.endswith(".jsonl"):
            continue
        content = blob.download_as_text()
        for line in content.strip().split("\n"):
            if not line.strip():
                continue
            try:
                result_obj = json.loads(line)

                # Primary: use custom_id from response (MUST be present)
                custom_id = result_obj.get("custom_id")
                if custom_id and custom_id in valid_case_ids:
                    case_id = custom_id
                    # Do NOT increment global_line — custom_id is authoritative
                elif custom_id:
                    # custom_id present but not in our manifest — skip
                    logger.warning(
                        "Unknown custom_id %s in result line %d, skipping",
                        custom_id[:12], global_line,
                    )
                    missing_custom_id_count += 1
                    continue
                else:
                    # NO custom_id — positional fallback is UNSAFE
                    missing_custom_id_count += 1
                    if missing_custom_id_count > len(case_id_order) * 0.1:
                        logger.error(
                            "HALTING: >10%% of batch results lack custom_id "
                            "(%d missing). Positional fallback is unreliable.",
                            missing_custom_id_count,
                        )
                        break
                    if global_line < len(case_id_order):
                        case_id = case_id_order[global_line]
                        logger.warning(
                            "No custom_id in line %d, UNSAFE positional fallback "
                            "(case_id=%s)", global_line, case_id[:12],
                        )
                        global_line += 1  # Only increment on positional fallback
                    else:
                        global_line += 1
                        continue

                # Extract the response content
                response = result_obj.get("response", {})
                candidates = response.get("candidates", [])
                if candidates:
                    content_parts = candidates[0].get("content", {}).get("parts", [])
                    if content_parts:
                        text_content = content_parts[0].get("text", "")
                        if text_content:
                            try:
                                parsed = json.loads(text_content)
                                if case_id in results:
                                    logger.warning(
                                        "Duplicate batch result for %s — keeping first",
                                        case_id[:12],
                                    )
                                else:
                                    results[case_id] = parsed
                            except (json.JSONDecodeError, ValueError) as parse_exc:
                                logger.warning(
                                    "Failed to parse JSON for case %s: %s",
                                    case_id, parse_exc,
                                )
                                failures += 1
                        else:
                            failures += 1
                    else:
                        failures += 1
                else:
                    failures += 1
            except (json.JSONDecodeError, KeyError, IndexError) as exc:
                logger.warning(
                    "Failed to parse result line %d: %s", global_line, exc,
                )
                global_line += 1
                failures += 1

    # Save results
    results_path = run_dir / "metadata_results.json"
    results_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    total = len(manifest)
    failure_rate = failures / total if total > 0 else 0.0
    logger.info(
        "Phase 2 complete: %d/%d successful (%.1f%% failure rate)",
        len(results), total, failure_rate * 100,
    )

    # Quality gate: abort if >10% failures
    if failure_rate > 0.10:
        logger.error(
            "QUALITY GATE FAILED: %.1f%% failure rate exceeds 10%% threshold. "
            "Aborting pipeline. Review results at %s",
            failure_rate * 100, results_path,
        )
        raise RuntimeError(
            f"Batch quality gate failed: {failure_rate:.1%} failure rate"
        )

    return results


# ---------------------------------------------------------------------------
# Phase 3: Online Processing Per Case
# ---------------------------------------------------------------------------


def _parse_batch_result_to_metadata(raw: dict) -> CaseMetadata:
    """Convert a raw batch result dict to a CaseMetadata dataclass."""
    field_names = {f.name for f in fields(CaseMetadata)}
    filtered = {k: v for k, v in raw.items() if k in field_names}

    # Convert structured headnotes list to JSON string for DB storage
    if isinstance(filtered.get("headnotes"), list):
        filtered["headnotes"] = json.dumps(filtered["headnotes"])

    # Parse judge names if present
    if "judge" in filtered and filtered["judge"] is not None:
        parsed = _parse_judge_names(filtered["judge"])
        if parsed is not None:
            filtered["judge"] = parsed

    return CaseMetadata(**filtered)


async def phase3_process_cases(
    run_id: str,
    manifest: list[ManifestEntry],
    metadata_results: dict[str, dict],
    rpm_limit: int = 30,
    concurrency: int = 1,
) -> dict[str, str]:
    """Process each case: validate, insert, chunk, embed, store, graph.

    Returns dict of case_id -> status ('success' or error message).
    """
    run_dir = BATCH_RUNS_DIR / run_id
    progress_path = run_dir / "progress.json"

    logger.info("=== PHASE 3: Online Processing (%d cases) ===", len(manifest))

    # Load existing progress for resume
    completed_cases: set[str] = set()
    if progress_path.exists():
        try:
            progress_data = json.loads(progress_path.read_text(encoding="utf-8"))
            completed_cases = set(progress_data.get("completed", []))
            logger.info("Resuming: %d cases already completed", len(completed_cases))
        except (json.JSONDecodeError, KeyError):
            pass

    # Initialize providers
    from app.core.dependencies import (  # noqa: E402
        get_embedder,
        get_graph_store,
        get_storage,
        get_vector_store,
    )
    from app.core.providers.llm.gemini import GeminiLLM  # noqa: E402

    # Use gemini-2.5-flash for online LLM calls (preview models unavailable on Vertex AI)
    llm = GeminiLLM(model=BATCH_MODEL)
    embedder = get_embedder()
    vector_store = get_vector_store()
    graph_store = get_graph_store()
    storage = get_storage()

    # Rate limiter for online LLM calls
    rate_limiter = AsyncRateLimiter(max_per_minute=rpm_limit)
    # Embedding RPM scales with LLM RPM (Vertex AI embedding quota is higher)
    embed_rpm = max(60, rpm_limit * 2)
    embed_rate_limiter = AsyncRateLimiter(max_per_minute=embed_rpm)

    # Disable FTS trigger for bulk performance
    await _disable_fts_trigger()

    statuses: dict[str, str] = {}
    processed_count = 0
    success_count = 0
    failure_count = 0
    credits_exhausted = False

    # Semaphore for concurrent case processing
    sem = asyncio.Semaphore(concurrency)
    progress_lock = asyncio.Lock()

    async def _process_one(idx: int, entry: ManifestEntry) -> None:
        nonlocal processed_count, success_count, failure_count, credits_exhausted

        if entry.case_id in completed_cases:
            return

        if entry.case_id not in metadata_results:
            logger.warning(
                "No batch metadata result for case %s, skipping", entry.case_id
            )
            async with progress_lock:
                statuses[entry.case_id] = "no_metadata"
            return

        async with sem:
            if _shutdown_event.is_set() or credits_exhausted:
                return

            logger.info(
                "[%d/%d] Processing case %s",
                idx + 1, len(manifest), entry.case_id,
            )

            try:
                status = await _process_single_case(
                    entry=entry,
                    raw_metadata=metadata_results[entry.case_id],
                    run_dir=run_dir,
                    llm=llm,
                    embedder=embedder,
                    vector_store=vector_store,
                    graph_store=graph_store,
                    storage=storage,
                    rate_limiter=rate_limiter,
                    embed_rate_limiter=embed_rate_limiter,
                )
                async with progress_lock:
                    statuses[entry.case_id] = status
                    if status == "success":
                        success_count += 1
                    else:
                        failure_count += 1

            except (PermissionError, gapi_exceptions.Forbidden) as perm_exc:
                err_str = str(perm_exc).lower()
                if "billing" in err_str or "403" in err_str or "permission" in err_str or isinstance(perm_exc, gapi_exceptions.Forbidden):
                    logger.error(
                        "GCP CREDITS EXHAUSTED or PERMISSION DENIED: %s\n"
                        "To resume:\n"
                        "  1. Switch to a GCP account with credits/billing enabled\n"
                        "  2. Run: python scripts/batch_ingest_vertex.py --resume %s\n",
                        perm_exc, run_id,
                    )
                    credits_exhausted = True
                    async with progress_lock:
                        statuses[entry.case_id] = f"billing_error: {perm_exc}"
                else:
                    raise

            except (RuntimeError, ConnectionError, TimeoutError, OSError, ValueError,
                    genai_errors.ClientError, httpx.TimeoutException, httpx.HTTPStatusError,
                    gapi_exceptions.ServiceUnavailable, gapi_exceptions.DeadlineExceeded,
                    ) as exc:
                exc_str = str(exc).lower()
                if "429" in exc_str or "resource_exhausted" in exc_str:
                    logger.warning(
                        "Rate limit (429) hit for case %s: %s — waiting 60s before retry",
                        entry.case_id, exc,
                    )
                    async with progress_lock:
                        statuses[entry.case_id] = f"rate_limited: {exc}"
                        failure_count += 1
                    await asyncio.sleep(60)
                elif "403" in exc_str and ("billing" in exc_str or "permission" in exc_str):
                    logger.error(
                        "GCP CREDITS EXHAUSTED: %s\n"
                        "To resume:\n"
                        "  1. Switch to a GCP account with credits/billing enabled\n"
                        "  2. Run: python scripts/batch_ingest_vertex.py --resume %s\n",
                        exc, run_id,
                    )
                    credits_exhausted = True
                    async with progress_lock:
                        statuses[entry.case_id] = f"billing_error: {exc}"
                else:
                    logger.error("Case %s failed: %s", entry.case_id, exc)
                    async with progress_lock:
                        statuses[entry.case_id] = f"error: {exc}"
                        failure_count += 1

            # Save progress after each case
            async with progress_lock:
                processed_count += 1
                if statuses.get(entry.case_id) == "success":
                    completed_cases.add(entry.case_id)
                _save_progress(progress_path, completed_cases, statuses)

                if processed_count % 10 == 0:
                    logger.info(
                        "Phase 3 progress: %d/%d processed (%d success, %d failed)",
                        processed_count, len(manifest), success_count, failure_count,
                    )
                if processed_count % 50 == 0:
                    gc.collect()
                    logger.debug("GC collected after %d cases", processed_count)

    try:
        # Run cases concurrently (bounded by semaphore)
        tasks = [
            asyncio.create_task(_process_one(idx, entry))
            for idx, entry in enumerate(manifest)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    finally:
        # Re-enable FTS trigger and rebuild
        try:
            await _enable_fts_trigger()
            await _rebuild_fts_vectors()
        except (RuntimeError, OSError, ConnectionError) as fts_exc:
            logger.error("FTS trigger rebuild failed: %s", fts_exc)

    logger.info(
        "Phase 3 complete: %d processed, %d success, %d failed",
        processed_count, success_count, failure_count,
    )
    return statuses


async def _process_single_case(
    entry: ManifestEntry,
    raw_metadata: dict[str, Any],
    run_dir: Path,
    llm: Any,
    embedder: Any,
    vector_store: Any,
    graph_store: Any,
    storage: Any,
    rate_limiter: AsyncRateLimiter,
    embed_rate_limiter: AsyncRateLimiter,
) -> str:
    """Process a single case through the full online pipeline.

    Returns 'success' or an error description.
    """
    case_id = entry.case_id
    full_text = entry.full_text

    # If full_text not in memory, reload from disk
    if not full_text:
        texts_dir = run_dir / "texts"
        text_path = texts_dir / f"{case_id}.txt"
        if text_path.exists():
            full_text = text_path.read_text(encoding="utf-8")
        if not full_text:
            return "error: no full text available"

    # A. Parse batch result -> CaseMetadata
    llm_meta = _parse_batch_result_to_metadata(raw_metadata)

    # Layer 4: Quick metadata sanity check
    if not llm_meta.title and not llm_meta.citation:
        logger.warning("Case %s: no title or citation in batch result, skipping", case_id)
        return "error: missing title and citation"

    # Pre-normalize LLM acts_cited to filter garbage before merge
    if llm_meta.acts_cited:
        llm_meta.acts_cited = normalize_acts_cited_list(llm_meta.acts_cited)

    # B. Validate: regex, cross-fields, propositions, merge with parquet
    validated_parquet = validate_parquet_data(entry.parquet_meta)
    metadata, provenance = merge_metadata(validated_parquet, llm_meta)
    metadata = validate_with_regex(metadata)
    metadata = validate_cross_fields(metadata)
    metadata = cross_validate_propositions(metadata)

    # Supplement acts_cited with regex extraction
    regex_acts = extract_acts_cited(full_text)
    if regex_acts:
        llm_acts = set(metadata.acts_cited or [])
        for ref in regex_acts:
            act_str = f"{ref.act_name}, {ref.year}" if ref.year else ref.act_name
            llm_acts.add(act_str)
        metadata.acts_cited = sorted(llm_acts)
        provenance["acts_cited"] = "batch_llm+regex"

    # Normalize acts_cited
    if metadata.acts_cited:
        metadata.acts_cited = normalize_acts_cited_list(metadata.acts_cited)
        provenance["acts_cited"] = provenance.get("acts_cited", "batch_llm") + "+normalized"

    # Enrich with cross-references
    if metadata.acts_cited:
        metadata.acts_cited = enrich_statute_cross_references(
            metadata.acts_cited, decision_year=metadata.year,
        )
        provenance["acts_cited"] = provenance.get("acts_cited", "batch_llm") + "+enriched"

    # Anonymization flags (text already anonymized in Phase 1; only detect sensitive case)
    anonymization_flags: list[str] = []
    if detect_sensitive_case(full_text, metadata):
        metadata.is_anonymized = True
        anonymization_flags.append("sensitive_case_detected")
    if anonymization_flags:
        metadata.anonymization_flags = anonymization_flags

    # Supplement cases_cited with regex extraction
    regex_citations = extract_citations(full_text)
    if regex_citations:
        llm_cases = set(metadata.cases_cited or [])
        for cit in regex_citations:
            llm_cases.add(cit.raw_text)
        metadata.cases_cited = sorted(llm_cases)
        provenance["cases_cited"] = "batch_llm+regex"

    # Compute extraction confidence
    extraction_confidence = compute_extraction_confidence(metadata)

    # C. Insert into PostgreSQL
    async with async_session_factory() as db:
        # Store PDF to storage backend
        from app.core.ingestion.pipeline import _safe_filename
        storage_dest = f"cases/{case_id}/{_safe_filename(entry.parquet_meta)}"
        try:
            storage_path = await storage.store(entry.pdf_local_path, storage_dest)
        except (OSError, PermissionError, FileNotFoundError, gapi_exceptions.GoogleAPICallError) as store_exc:
            logger.warning("Failed to store PDF for %s: %s", case_id, store_exc)
            storage_path = entry.pdf_local_path

        resolved_case_id, already_ingested = await _insert_case(
            db, case_id, metadata, full_text, storage_path, entry.parquet_meta,
            provenance=provenance, text_hash=entry.text_hash,
            extraction_confidence=extraction_confidence,
            page_map=entry.page_map,
        )
        if resolved_case_id != case_id:
            logger.info(
                "case_id resolved: %s -> %s (citation match)",
                case_id[:12], resolved_case_id[:12],
            )
        case_id = resolved_case_id  # Use resolved ID for all subsequent ops

        if already_ingested:
            logger.info("Case %s already fully ingested, skipping", metadata.citation)
            return "success"

        # Mark as processing
        async with db.begin_nested():
            await db.execute(
                sa_text("UPDATE cases SET ingestion_status = 'processing', updated_at = NOW() WHERE id = :id"),
                {"id": case_id},
            )

        db_committed = False
        vectors_upserted = False
        try:
            # D. Chunk
            sections = detect_judgment_sections(full_text)
            chunks = chunk_judgment(full_text, sections, case_id=case_id)
            logger.info("case_id=%s: %d sections, %d chunks", case_id, len(sections), len(chunks))

            # Persist sections + statute interpretations + citation equivalents
            await db.execute(
                sa_text("DELETE FROM case_sections WHERE case_id = :case_id"),
                {"case_id": str(case_id)},
            )
            await _persist_sections(str(case_id), sections, db)
            await _persist_statute_interpretations(str(case_id), metadata, db)
            citation_equivalents = _extract_citation_equivalents(full_text, str(case_id))
            await db.execute(
                sa_text("DELETE FROM case_citation_equivalents WHERE case_id = :case_id"),
                {"case_id": str(case_id)},
            )
            if citation_equivalents:
                await _persist_citation_equivalents(citation_equivalents, db)

            # E. Contextual prefixes
            chunk_dicts = [{"text": c.text, "section_type": c.section_type} for c in chunks]
            doc_meta = {
                "title": metadata.title or "",
                "citation": metadata.citation or "",
                "court": metadata.court or "",
                "year": metadata.year or 0,
            }
            try:
                contextualized = await asyncio.wait_for(
                    batch_contextualize_chunks(
                        chunk_dicts, doc_meta, llm, document_type="case_law",
                        rate_limiter=rate_limiter,
                    ),
                    timeout=300.0,  # 5 min max for contextual prefixes
                )
                contextualized_texts = [c["contextualized_text"] for c in contextualized]
            except (RuntimeError, TimeoutError, ConnectionError, asyncio.TimeoutError) as ctx_exc:
                logger.warning("Contextual embedding failed for %s: %s", case_id, ctx_exc)
                contextualized_texts = None

            # F. Embed chunks
            embeddings = await asyncio.wait_for(
                _embed_chunks(
                    chunks, embedder, rate_limiter=embed_rate_limiter,
                    texts_override=contextualized_texts,
                ),
                timeout=300.0,
            )
            if len(embeddings) != len(chunks):
                raise RuntimeError(
                    f"Embedding count mismatch: {len(embeddings)} for {len(chunks)} chunks"
                )

            # Layer 4: Spot-check embedding dimensions
            if embeddings and len(embeddings[0]) != 1536:
                return f"error: embedding dimension {len(embeddings[0])} != 1536"

            # G. Upsert chunk vectors
            new_vector_ids = [f"{case_id}_{chunk.chunk_index}" for chunk in chunks]
            await _upsert_vectors(
                case_id, chunks, embeddings, metadata, vector_store,
                page_map=entry.page_map, full_text=full_text,
            )
            vectors_upserted = True

            # H. Proposition/ratio/headnote vectors
            proposition_vectors_failed = False
            try:
                prop_count, prop_vector_ids = await _upsert_proposition_vectors(
                    case_id, metadata, embedder, vector_store,
                    rate_limiter=embed_rate_limiter,
                )
                if prop_count:
                    logger.info("Created %d proposition vectors for %s", prop_count, case_id)
                new_vector_ids.extend(prop_vector_ids)
            except (RuntimeError, ConnectionError, TimeoutError) as prop_exc:
                logger.warning("Proposition vector upsert failed for %s: %s", case_id, prop_exc)
                proposition_vectors_failed = True

            # I. Stale vector cleanup
            try:
                await vector_store.delete_by_metadata(
                    {"case_id": case_id},
                    exclude_ids=new_vector_ids,
                )
            except (RuntimeError, ConnectionError) as cleanup_exc:
                logger.warning("Stale vector cleanup failed for %s: %s", case_id, cleanup_exc)

            # J. RAPTOR summaries
            try:
                section_dicts = [
                    {"section_type": s.type, "content": s.text}
                    for s in sections
                ]
                summaries = await generate_section_summaries(
                    str(case_id), section_dicts, llm,
                )
                if summaries:
                    summary_texts = [s["summary_text"] for s in summaries]
                    await embed_rate_limiter.acquire()
                    summary_embeddings = await embedder.embed_batch(summary_texts)
                    base_meta = {
                        "title": (metadata.title or "")[:200],
                        "citation": metadata.citation or "",
                        "court": metadata.court or "",
                        "year": metadata.year or 0,
                        "case_type": metadata.case_type or "",
                        "bench_type": metadata.bench_type or "",
                        "disposal_nature": metadata.disposal_nature or "",
                        "jurisdiction": metadata.jurisdiction or "",
                    }
                    summary_vectors = build_pinecone_summary_vectors(
                        str(case_id), summaries, summary_embeddings, base_meta,
                    )
                    await vector_store.upsert(summary_vectors)
                    logger.info(
                        "case_id=%s: %d RAPTOR section summaries stored",
                        case_id, len(summaries),
                    )
            except (RuntimeError, ConnectionError, TimeoutError) as raptor_exc:
                logger.warning(
                    "RAPTOR summary generation failed for %s: %s", case_id, raptor_exc,
                )

            # K. Update chunk_count, set ingestion_status
            _REVIEW_THRESHOLD = 0.5
            if extraction_confidence < _REVIEW_THRESHOLD:
                final_status = "needs_review"
            elif proposition_vectors_failed:
                final_status = "needs_review"
            else:
                final_status = "complete"
            await db.execute(
                sa_text(
                    "UPDATE cases SET chunk_count = :count, ingestion_status = :status, "
                    "updated_at = NOW() WHERE id = :id"
                ),
                {"count": len(chunks), "status": final_status, "id": case_id},
            )

            # Commit DB
            try:
                await db.commit()
                db_committed = True
            except (RuntimeError, OSError, ConnectionError) as commit_exc:
                logger.error("DB commit failed for case_id=%s: %s", case_id, commit_exc)
                raise

            # L. Citation graph (non-critical)
            try:
                await asyncio.wait_for(
                    _build_citation_graph(case_id, metadata, full_text, graph_store),
                    timeout=60.0,
                )
                if citation_equivalents:
                    await _link_citation_equivalents(
                        case_id, metadata.citation, citation_equivalents, graph_store,
                    )
            except (OSError, ConnectionError, RuntimeError, asyncio.TimeoutError) as graph_exc:
                logger.warning("Citation graph build failed for %s: %s", case_id, graph_exc)

        except (RuntimeError, ConnectionError, TimeoutError, OSError, ValueError) as pipeline_exc:
            if not db_committed:
                try:
                    await db.rollback()
                except (RuntimeError, OSError, ConnectionError):
                    logger.error("Rollback failed for case_id=%s", case_id)
                if vectors_upserted:
                    try:
                        await vector_store.delete_by_metadata({"case_id": case_id})
                    except (RuntimeError, ConnectionError, OSError):
                        logger.error("Failed to clean orphan vectors for %s", case_id)
            raise pipeline_exc

    return "success"


def _save_progress(
    progress_path: Path,
    completed_cases: set[str],
    statuses: dict[str, str],
) -> None:
    """Save progress to disk atomically for resume support.

    Writes to a temp file first, then atomically replaces the target.
    Prevents corrupted JSON from partial writes (OOM, power loss, SIGKILL).
    """
    data = {
        "completed": sorted(completed_cases),
        "statuses": statuses,
        "saved_at": datetime.now().isoformat(),
    }
    tmp_path = progress_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(str(tmp_path), str(progress_path))  # atomic on NTFS + Linux


# ---------------------------------------------------------------------------
# Phase 4: Quality Check
# ---------------------------------------------------------------------------


async def phase4_quality_check(run_id: str) -> dict[str, Any]:
    """Sample 10 completed cases and verify data integrity.

    Checks: 5 vector types in Pinecone, key PG fields, chunk_count, confidence.
    """
    run_dir = BATCH_RUNS_DIR / run_id
    logger.info("=== PHASE 4: Quality Check for %s ===", run_id)

    # Load progress
    progress_path = run_dir / "progress.json"
    if not progress_path.exists():
        logger.error("No progress.json found for run %s", run_id)
        return {"error": "no progress file"}

    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    completed = [
        cid for cid, status in progress.get("statuses", {}).items()
        if status == "success"
    ]

    if not completed:
        logger.error("No successfully completed cases to check")
        return {"error": "no completed cases"}

    # Sample up to 10
    sample_size = min(10, len(completed))
    sample_ids = random.sample(completed, sample_size)
    logger.info("Sampling %d cases for quality check", sample_size)

    from app.core.dependencies import get_vector_store  # noqa: E402
    vector_store = get_vector_store()

    report: dict[str, Any] = {
        "run_id": run_id,
        "total_completed": len(completed),
        "sample_size": sample_size,
        "checks": [],
    }

    pass_count = 0
    for case_id in sample_ids:
        check: dict[str, Any] = {"case_id": case_id, "issues": []}

        # PG checks
        async with async_session_factory() as db:
            row = await db.execute(
                sa_text(
                    "SELECT title, citation, court, year, chunk_count, "
                    "extraction_confidence, ingestion_status "
                    "FROM cases WHERE id = :id"
                ),
                {"id": case_id},
            )
            case_row = row.fetchone()

        if not case_row:
            check["issues"].append("Case not found in PostgreSQL")
            report["checks"].append(check)
            continue

        title, citation, court, year, chunk_count, confidence, ing_status = case_row

        # Check key fields non-null
        if not title:
            check["issues"].append("title is NULL")
        if not citation:
            check["issues"].append("citation is NULL")
        if not court:
            check["issues"].append("court is NULL")
        if not year:
            check["issues"].append("year is NULL")

        # Check chunk_count
        if not chunk_count or chunk_count == 0:
            check["issues"].append(f"chunk_count is {chunk_count}")

        # Check extraction_confidence
        if confidence is not None and confidence < 0.5:
            check["issues"].append(f"extraction_confidence {confidence:.3f} < 0.5")

        # Check vector types in Pinecone
        expected_types = ["chunk", "proposition", "ratio", "headnote", "summary"]
        for vtype in expected_types:
            try:
                results = await vector_store.query_by_metadata(
                    {"case_id": case_id, "vector_type": vtype},
                    top_k=1,
                )
                if not results:
                    check["issues"].append(f"No {vtype} vectors found")
            except (AttributeError, NotImplementedError):
                # If vector store doesn't support query_by_metadata, try alternative
                try:
                    # Use a zero vector query with metadata filter
                    results = await vector_store.query(
                        vector=[0.0] * 1536,
                        top_k=1,
                        filter={"case_id": case_id, "vector_type": vtype},
                    )
                    if not results:
                        check["issues"].append(f"No {vtype} vectors found")
                except (RuntimeError, ConnectionError, TimeoutError) as vec_exc:
                    check["issues"].append(f"Vector check failed for {vtype}: {vec_exc}")

        # Check chunk_count matches actual vectors
        if chunk_count and chunk_count > 0:
            try:
                chunk_results = await vector_store.query(
                    vector=[0.0] * 1536,
                    top_k=chunk_count + 10,
                    filter={"case_id": case_id, "vector_type": "chunk"},
                )
                actual_chunks = len(chunk_results) if chunk_results else 0
                if actual_chunks != chunk_count:
                    check["issues"].append(
                        f"chunk_count mismatch: PG={chunk_count}, Pinecone={actual_chunks}"
                    )
            except (RuntimeError, ConnectionError, TimeoutError) as count_exc:
                check["issues"].append(f"Chunk count verification failed: {count_exc}")

        if not check["issues"]:
            check["status"] = "PASS"
            pass_count += 1
        else:
            check["status"] = "FAIL"

        report["checks"].append(check)

    report["pass_rate"] = f"{pass_count}/{sample_size}"
    report["overall"] = "PASS" if pass_count == sample_size else "FAIL"

    # Print report
    print("\n" + "=" * 60)
    print(f"QUALITY CHECK REPORT: {run_id}")
    print("=" * 60)
    print(f"Total completed cases: {len(completed)}")
    print(f"Sample size: {sample_size}")
    print(f"Pass rate: {pass_count}/{sample_size}")
    print(f"Overall: {report['overall']}")
    print("-" * 60)
    for check in report["checks"]:
        status_str = check["status"]
        case_str = check["case_id"][:12]
        if check.get("issues"):
            issues_str = "; ".join(check["issues"])
            print(f"  [{status_str}] {case_str}... : {issues_str}")
        else:
            print(f"  [{status_str}] {case_str}...")
    print("=" * 60)

    # Save report
    report_path = run_dir / "quality_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    logger.info("Quality report saved to %s", report_path)

    return report


# ---------------------------------------------------------------------------
# Resume support
# ---------------------------------------------------------------------------


def _load_manifest_from_disk(run_id: str) -> list[ManifestEntry]:
    """Reload manifest and texts from a previous run directory."""
    run_dir = BATCH_RUNS_DIR / run_id
    manifest_path = run_dir / "manifest.json"
    texts_dir = run_dir / "texts"

    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.json found at {manifest_path}")

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries: list[ManifestEntry] = []

    for item in manifest_data:
        case_id = item["case_id"]
        # Load full text from disk
        text_path = texts_dir / f"{case_id}.txt"
        full_text = text_path.read_text(encoding="utf-8") if text_path.exists() else ""

        entries.append(ManifestEntry(
            case_id=case_id,
            pdf_local_path=item.get("pdf_local_path", ""),
            gcs_pdf_uri=item.get("gcs_pdf_uri", ""),
            text_hash=item.get("text_hash", ""),
            full_text=full_text,
            parquet_meta=item.get("parquet_meta", {}),
            quality_tier=item.get("quality_tier", "medium"),
            page_count=item.get("page_count", 0),
            page_map=item.get("page_map", []),
            char_count=item.get("char_count", 0),
        ))

    return entries


def _load_metadata_results(run_id: str) -> dict[str, dict]:
    """Load batch metadata results from disk."""
    run_dir = BATCH_RUNS_DIR / run_id
    results_path = run_dir / "metadata_results.json"
    if not results_path.exists():
        raise FileNotFoundError(f"No metadata_results.json found at {results_path}")
    return json.loads(results_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def run_pipeline(
    year: int | None = None,
    all_years: bool = False,
    limit: int = 1000,
    resume: str | None = None,
    quality_check: str | None = None,
    dry_run: bool = False,
    rpm_limit: int = 30,
    concurrency: int = 1,
) -> None:
    """Main pipeline orchestrator."""
    # Initialize shutdown event inside the running event loop (not at import time)
    _init_shutdown_event()

    # Install signal handlers
    loop = asyncio.get_running_loop()
    handler = _make_shutdown_handler(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, handler)
        except (OSError, ValueError):
            pass  # May fail on Windows for SIGTERM

    # Enforce Vertex AI for batch pipeline (except quality-check which is read-only)
    if not quality_check and not dry_run and not settings.gemini_use_vertexai:
        logger.error(
            "GEMINI_USE_VERTEXAI must be true for batch ingestion. "
            "Set GEMINI_USE_VERTEXAI=true in .env"
        )
        return

    # Quality check mode
    if quality_check:
        await phase4_quality_check(quality_check)
        return

    # Resume mode: skip Phase 1+2, go straight to Phase 3
    if resume:
        logger.info("Resuming Phase 3 from run: %s", resume)
        manifest = _load_manifest_from_disk(resume)
        metadata_results = _load_metadata_results(resume)
        statuses = await phase3_process_cases(
            resume, manifest, metadata_results,
            rpm_limit=rpm_limit, concurrency=concurrency,
        )
        logger.info(
            "Resume complete: %d success, %d failed",
            sum(1 for s in statuses.values() if s == "success"),
            sum(1 for s in statuses.values() if s != "success"),
        )
        return

    # Determine years to process
    years: list[int] = []
    if all_years:
        years = list(range(1950, 2026))
    elif year is not None:
        years = [year]
    else:
        logger.error("Must specify --year, --all, --resume, or --quality-check")
        return

    for yr in years:
        if _shutdown_event.is_set():
            logger.warning("Shutdown requested — stopping year loop")
            break

        logger.info("=" * 60)
        logger.info("Processing year %d", yr)
        logger.info("=" * 60)

        # Phase 1: Extract and upload
        run_id, manifest = await phase1_extract_and_upload(yr, limit, dry_run=dry_run)

        if not manifest:
            logger.info("No cases to process for year %d, skipping", yr)
            continue

        if dry_run:
            logger.info(
                "DRY RUN complete for year %d: %d cases would be processed",
                yr, len(manifest),
            )
            continue

        if _shutdown_event.is_set():
            break

        # Phase 2: Batch metadata extraction
        try:
            metadata_results = await phase2_batch_metadata(run_id, manifest)
        except (RuntimeError, KeyboardInterrupt) as phase2_exc:
            logger.error("Phase 2 failed for year %d: %s", yr, phase2_exc)
            continue

        if _shutdown_event.is_set():
            break

        # Layer 3: Quality gate — validate metadata before spending on Phase 3
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
            from ingestion.quality_gates import validate_batch_metadata

            qg_report = validate_batch_metadata(metadata_results)
            if not qg_report.passed:
                logger.error("QUALITY GATE FAILED between Phase 2 and Phase 3:")
                for f in qg_report.failures:
                    logger.error("  %s", f)
                logger.error("Fix issues and resume with: --resume %s", run_id)
                continue
            logger.info("Quality gate passed: %s", qg_report.checks)
            for w in qg_report.warnings:
                logger.warning("  QG WARNING: %s", w)
        except ImportError:
            logger.warning("quality_gates module not found, skipping Layer 3 check")

        # Phase 3: Online processing
        statuses = await phase3_process_cases(
            run_id, manifest, metadata_results,
            rpm_limit=rpm_limit, concurrency=concurrency,
        )

        success = sum(1 for s in statuses.values() if s == "success")
        failed = sum(1 for s in statuses.values() if s != "success")
        logger.info(
            "Year %d complete: %d success, %d failed (run_id=%s)",
            yr, success, failed, run_id,
        )

        # Phase 4: Auto quality check
        if success >= 10:
            await phase4_quality_check(run_id)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vertex AI batch ingestion pipeline for Indian Supreme Court judgments",
    )
    parser.add_argument("--year", type=int, help="Ingest a specific year")
    parser.add_argument("--all", action="store_true", help="Ingest all remaining years (1950-2025)")
    parser.add_argument("--limit", type=int, default=1000, help="Max cases per run (default: 1000)")
    parser.add_argument("--resume", type=str, help="Resume Phase 3 from a previous batch run directory name")
    parser.add_argument("--quality-check", type=str, help="Run quality check on a completed run")
    parser.add_argument("--dry-run", action="store_true", help="Phase 1 only, no API calls")
    parser.add_argument("--rpm-limit", type=int, default=30, help="Gemini RPM limit for online calls (default: 30)")
    parser.add_argument("--concurrency", type=int, default=1, help="Concurrent cases in Phase 3 (default: 1)")

    args = parser.parse_args()

    asyncio.run(
        run_pipeline(
            year=args.year,
            all_years=args.all,
            limit=args.limit,
            resume=args.resume,
            quality_check=args.quality_check,
            dry_run=args.dry_run,
            rpm_limit=args.rpm_limit,
            concurrency=args.concurrency,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Fatal error in batch ingestion pipeline")
        sys.exit(1)
