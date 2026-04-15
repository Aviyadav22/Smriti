"""Batch ingestion orchestrator using Gemini Batch API.

⚠️  DEPRECATED — DO NOT USE FOR PRODUCTION INGESTION  ⚠️

This approach was evaluated against the standard pipeline (individual Flash
calls with responseSchema enforcement) on 10 SC judgments (2023) and found
to produce LOWER quality metadata:

  - Neutral citations (INSC) missing in 7/10 cases (pipeline gets 8/10)
  - is_reportable always null (pipeline correctly fills 7/10)
  - 29% fewer cases_cited, 3.5x fewer citation_treatments
  - 35% fewer legal_propositions, 52% fewer arguments_raised
  - Root cause: Gemini Batch API does NOT support responseSchema in JSONL
    requests, so structured output is schema-in-prompt (less reliable)
  - Batch requires Pro model on Tier 1 (4x more expensive than Flash)

Use the standard pipeline instead: scripts/ingest_s3.py

Kept for reference only. See comparison data in:
  - data/batch_results_10pdf.jsonl  (batch output)
  - data/pipeline_results_10pdf.json (pipeline output)

Original description:
Three-phase CLI for 43K case ingestion at 50% cost:
  submit  — Extract text, upload PDFs, submit batch LLM jobs
  poll    — Poll batch jobs, collect results
  process — Feed cached results into existing pipeline via MockLLM

Usage:
  python -m scripts.batch_ingest submit --year-from 2015 --year-to 2023
  python -m scripts.batch_ingest poll --interval 60
  python -m scripts.batch_ingest process --year-from 2015 --year-to 2023
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import tempfile
import time
from pathlib import Path

from google import genai
from google.genai import types as genai_types

# Ensure backend is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.ingestion.pdf import extract_and_score
from app.core.ingestion.pipeline import _compute_text_hash
from app.core.legal.prompts import (
    METADATA_EXTRACTION_SYSTEM,
    METADATA_EXTRACTION_USER,
    METADATA_OUTPUT_SCHEMA,
)
from scripts.batch_state import BatchStateDB
from scripts.ingest_s3 import (
    _build_key_pool,
    _strip_language_suffix,
    download_year_data,
    extract_tar,
    load_parquet_metadata,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("batch_ingest")

S3_BUCKET = "s3://indian-supreme-court-judgments"
WAVE_SIZE = 5000  # Max docs per wave per project (20GB / ~2MB avg = ~10K, use 5K for safety)
BATCH_TOKEN_LIMIT = 200  # Docs per batch job (conservative for Tier 1 3M token limit)


def _normalize_doc_key(year: int, pdf_path: Path) -> str:
    """Consistent forward-slash doc_key, matching ingest_s3.py convention."""
    return f"year={year}/{pdf_path.name}"


# ---------------------------------------------------------------------------
# Phase 1: Submit
# ---------------------------------------------------------------------------


async def _upload_pdf(client: genai.Client, pdf_path: Path) -> str:
    """Upload a PDF to Gemini Files API. Returns the file URI."""
    uploaded = await asyncio.to_thread(
        client.files.upload,
        file=str(pdf_path),
    )
    return uploaded.name  # e.g. "files/abc123"


def _build_batch_request_entry(doc_key: str, file_uri: str) -> dict:
    """Build one entry for the batch JSONL file.

    Note: Batch API does not support responseSchema in JSONL requests.
    We include the JSON schema in the prompt text instead and use
    responseMimeType to enforce JSON output format.
    """
    schema_text = json.dumps(METADATA_OUTPUT_SCHEMA, indent=2)
    prompt = METADATA_EXTRACTION_USER.format(judgment_text="[See attached PDF document]")
    prompt += (
        "\n\nYou MUST return your response as valid JSON matching this schema exactly:\n"
        f"```json\n{schema_text}\n```"
    )
    return {
        "key": doc_key,
        "request": {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"file_data": {"file_uri": file_uri, "mime_type": "application/pdf"}},
                        {"text": prompt},
                    ],
                }
            ],
            "systemInstruction": {"parts": [{"text": METADATA_EXTRACTION_SYSTEM}]},
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
            },
        },
    }


async def _load_existing_text_hashes() -> set[str]:
    """Batch-fetch all existing text hashes from PG into a set for O(1) dedup."""
    from sqlalchemy import text

    from app.db.postgres import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(text("SELECT text_hash FROM cases WHERE text_hash IS NOT NULL"))
        hashes = {row[0] for row in result.fetchall()}
    logger.info("Loaded %d existing text hashes for dedup", len(hashes))
    return hashes


async def submit_year(
    year: int,
    api_keys: list[str],
    state_db: BatchStateDB,
    data_dir: Path,
    *,
    wave_size: int = WAVE_SIZE,
    concurrency: int = 10,
) -> None:
    """Phase 1: Extract, upload, and submit batch jobs for one year."""
    # Download tar and parquet (reuse ingest_s3 helpers — correct S3 paths)
    # download_year_data is sync — wrap in thread to avoid blocking event loop
    tar_path, parquet_path = await asyncio.to_thread(download_year_data, year, data_dir)
    if tar_path is None:
        logger.error("Failed to download tar for year %d, skipping", year)
        return
    extract_dir = data_dir / f"year={year}" / "extracted"

    # extract_tar is also sync
    pdf_paths = await asyncio.to_thread(extract_tar, tar_path, extract_dir)
    logger.info("Year %d: %d PDFs extracted", year, len(pdf_paths))

    # Load parquet metadata (sync — wrap in thread)
    metadata_map = await asyncio.to_thread(load_parquet_metadata, parquet_path)
    stem_index: dict[str, str] = {}
    for key in metadata_map:
        stem = Path(str(key)).stem
        stem_index[stem] = key
        stripped = _strip_language_suffix(stem)
        if stripped != stem:
            stem_index[stripped] = key

    # Filter out already-uploaded/completed docs
    new_pdfs: list[Path] = []
    for pdf_path in pdf_paths:
        doc_key = _normalize_doc_key(year, pdf_path)
        existing = state_db.get_doc(doc_key)
        if existing and existing["status"] not in ("error", "batch_failed"):
            continue  # Already uploaded or further along
        new_pdfs.append(pdf_path)
    logger.info(
        "Year %d: %d new PDFs to process (skipping %d already tracked)",
        year,
        len(new_pdfs),
        len(pdf_paths) - len(new_pdfs),
    )

    # Batch-fetch existing text hashes for O(1) dedup (instead of per-PDF DB query)
    existing_hashes = await _load_existing_text_hashes()

    # Process in waves, round-robin across API keys
    clients = [genai.Client(api_key=key) for key in api_keys]
    key_idx = 0

    for wave_start in range(0, len(new_pdfs), wave_size):
        wave = new_pdfs[wave_start : wave_start + wave_size]
        client = clients[key_idx % len(clients)]
        current_key_idx = key_idx % len(clients)
        key_idx += 1

        logger.info(
            "Year %d wave %d: %d PDFs (API key %d)",
            year,
            wave_start // wave_size + 1,
            len(wave),
            current_key_idx,
        )

        # Upload PDFs and extract text concurrently
        sem = asyncio.Semaphore(concurrency)
        batch_entries: list[dict] = []

        async def _process_pdf(pdf_path: Path) -> dict | None:
            doc_key = _normalize_doc_key(year, pdf_path)
            async with sem:
                try:
                    # Extract text for dedup check
                    text_quality = await extract_and_score(str(pdf_path))
                    if not text_quality.text or text_quality.char_count < 100:
                        logger.warning(
                            "Skipping %s: too short (%d chars)", doc_key, text_quality.char_count
                        )
                        return None

                    text_hash = _compute_text_hash(text_quality.text)

                    # Dedup against pre-loaded hash set (O(1) lookup, no DB round-trip)
                    if text_hash in existing_hashes:
                        logger.info("Skipping %s: duplicate text_hash", doc_key)
                        return None

                    # Upload PDF to Gemini Files API
                    file_uri = await _upload_pdf(client, pdf_path)

                    # Match parquet metadata
                    from scripts.ingest_s3 import _match_pdf_to_metadata

                    parquet_meta = _match_pdf_to_metadata(pdf_path, metadata_map, stem_index)

                    # Store in state DB
                    state_db.insert_doc(
                        doc_key=doc_key,
                        year=year,
                        file_uri=file_uri,
                        text_hash=text_hash,
                        full_text_len=text_quality.char_count,
                        parquet_meta=parquet_meta,
                        pdf_path=str(pdf_path),
                        api_key_index=current_key_idx,
                    )

                    # Build batch request entry
                    return _build_batch_request_entry(doc_key, file_uri)

                except Exception as exc:
                    logger.error("Failed to process %s: %s", doc_key, exc)
                    return None

        tasks = [_process_pdf(p) for p in wave]
        results = await asyncio.gather(*tasks)
        batch_entries = [r for r in results if r is not None]
        logger.info("Wave complete: %d entries ready for batch submission", len(batch_entries))

        if not batch_entries:
            continue

        # Submit in sub-batches (respect enqueued token limit)
        for batch_start in range(0, len(batch_entries), BATCH_TOKEN_LIMIT):
            sub_batch = batch_entries[batch_start : batch_start + BATCH_TOKEN_LIMIT]

            # Write JSONL to temp file and upload
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".jsonl", delete=False, dir=str(data_dir)
            ) as f:
                for entry in sub_batch:
                    f.write(json.dumps(entry) + "\n")
                jsonl_path = f.name

            # Upload JSONL file to Gemini Files API
            jsonl_file = await asyncio.to_thread(
                client.files.upload,
                file=jsonl_path,
                config={"mime_type": "jsonl"},
            )

            # Submit batch job
            batch_job = await asyncio.to_thread(
                client.batches.create,
                model=f"models/{settings.gemini_model}",
                src=jsonl_file.name,
                config=genai_types.CreateBatchJobConfig(
                    display_name=f"smriti-{year}-w{wave_start // wave_size}-b{batch_start // BATCH_TOKEN_LIMIT}",
                ),
            )

            job_name = batch_job.name
            state_db.insert_job(job_name, current_key_idx, len(sub_batch))

            # Update doc statuses
            for entry in sub_batch:
                state_db.update_doc_status(
                    entry["key"],
                    "submitted",
                    batch_job_name=job_name,
                )

            logger.info(
                "Submitted batch job %s: %d requests (key %d)",
                job_name,
                len(sub_batch),
                current_key_idx,
            )

            # Clean up temp file
            Path(jsonl_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Phase 2: Poll
# ---------------------------------------------------------------------------


async def poll_jobs(
    api_keys: list[str],
    state_db: BatchStateDB,
    *,
    interval: int = 60,
) -> None:
    """Phase 2: Poll batch jobs and collect results."""
    clients = [genai.Client(api_key=key) for key in api_keys]

    while True:
        pending = state_db.get_pending_jobs()
        if not pending:
            logger.info("All batch jobs completed.")
            break

        logger.info("Polling %d pending batch jobs...", len(pending))

        for job_row in pending:
            job_name = job_row["job_name"]
            key_idx = job_row["api_key_index"]
            client = clients[key_idx]

            try:
                job = await asyncio.to_thread(client.batches.get, name=job_name)
            except Exception as exc:
                logger.error("Failed to poll %s: %s", job_name, exc)
                continue

            state_str = str(job.state) if job.state else "UNKNOWN"

            if job.state in genai_types.JOB_STATES_SUCCEEDED:
                logger.info("Job %s SUCCEEDED", job_name)
                state_db.update_job_status(job_name, "succeeded")
                await _collect_results(client, job, state_db)

            elif job.state in genai_types.JOB_STATES_ENDED:
                # Failed, cancelled, or expired
                error_msg = str(job.error) if job.error else state_str
                logger.error("Job %s ended with state %s: %s", job_name, state_str, error_msg)
                state_db.update_job_status(job_name, "failed")
                # Mark all docs in this job as failed
                docs = state_db.get_docs_by_status("submitted")
                for doc in docs:
                    if doc["batch_job_name"] == job_name:
                        state_db.mark_error(doc["doc_key"], f"batch_job_{state_str}: {error_msg}")
            else:
                logger.info("Job %s still %s", job_name, state_str)

        # Wait before next poll
        logger.info("Sleeping %ds before next poll...", interval)
        await asyncio.sleep(interval)


async def _collect_results(
    client: genai.Client,
    job: genai_types.BatchJob,
    state_db: BatchStateDB,
) -> None:
    """Download and store batch job results."""
    # Results are available via job.dest — either inline or file-based
    # For file-based: download the output file
    if job.dest and job.dest.gcs_uri:
        # File-based results — not typical for AI Studio, handle just in case
        logger.warning("GCS-based results not implemented, skipping job %s", job.name)
        return

    # For inline/file results from AI Studio: re-read via the dest file
    if job.dest and hasattr(job.dest, "file_name") and job.dest.file_name:
        result_file_name = job.dest.file_name
        # Download the result file content
        try:
            result_content = await asyncio.to_thread(
                client.files.download,
                file=result_file_name,
            )
            # Parse JSONL results
            for line in result_content.decode("utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                entry = json.loads(line)
                _process_result_entry(entry, state_db)
        except Exception as exc:
            logger.error("Failed to download results for job %s: %s", job.name, exc)
            return
    else:
        # Try inline responses
        if hasattr(job, "dest") and job.dest and hasattr(job.dest, "inlined_responses"):
            for entry in job.dest.inlined_responses or []:
                _process_result_entry(entry, state_db)
        else:
            logger.warning("No results found for job %s (dest=%s)", job.name, job.dest)


def _process_result_entry(entry: dict, state_db: BatchStateDB) -> None:
    """Process a single batch result entry and store it."""
    doc_key = entry.get("key", "")
    if not doc_key:
        logger.warning("Batch result missing 'key' field: %s", str(entry)[:200])
        return

    response = entry.get("response", {})

    # Extract the structured JSON from the response
    # Batch API wraps results in: {response: {candidates: [{content: {parts: [{text: "..."}]}}]}}
    try:
        candidates = response.get("candidates", [])
        if not candidates:
            state_db.mark_error(doc_key, "No candidates in batch response")
            return

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            state_db.mark_error(doc_key, "No parts in batch response")
            return

        text_result = parts[0].get("text", "")
        if not text_result:
            state_db.mark_error(doc_key, "Empty text in batch response")
            return

        result_dict = json.loads(text_result)

        # Sanity check: must have at least title or citation
        if not result_dict.get("title") and not result_dict.get("citation"):
            state_db.mark_error(doc_key, "Result missing both title and citation")
            return

        state_db.store_result(doc_key, result_dict)

    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        state_db.mark_error(doc_key, f"Failed to parse batch result: {exc}")


# ---------------------------------------------------------------------------
# Phase 3: Process
# ---------------------------------------------------------------------------


async def process_completed(
    api_keys: list[str],
    state_db: BatchStateDB,
    *,
    year_from: int = 2015,
    year_to: int = 2023,
    concurrency: int = 20,
    rpm_limit: int = 0,
) -> None:
    """Phase 3: Feed cached batch results into existing pipeline."""
    import itertools

    from app.core.ingestion.pipeline import ingest_judgment
    from app.core.ingestion.rate_limiter import RateLimiterPool
    from app.core.providers.embeddings.gemini import GeminiEmbedder
    from app.core.providers.graph.neo4j_store import Neo4jStore
    from app.core.providers.storage.local_store import LocalFileStorage
    from app.core.providers.vector.pinecone_store import PineconeStore
    from app.db.postgres import async_session_factory
    from scripts.batch_llm import BatchCachedLLM
    from scripts.ingest_s3 import IngestTracker

    # Initialize shared providers (real — only LLM is mocked)
    embedder_pool = [GeminiEmbedder(api_key=key) for key in api_keys]
    vector_store = PineconeStore()
    graph_store = Neo4jStore()
    storage = LocalFileStorage()
    tracker = IngestTracker()

    # Embed rate limiter (LLM limiter not needed — calls are instant)
    embed_limiter_pool: RateLimiterPool | None = None
    if rpm_limit > 0:
        embed_limiter_pool = RateLimiterPool(rpm_per_key=rpm_limit * 5)

    # Collect all completed docs for the year range
    all_docs: list[dict] = []
    for year in range(year_from, year_to + 1):
        all_docs.extend(state_db.get_docs_by_status("completed", year=year))
    logger.info("Phase 3: %d completed docs to process", len(all_docs))

    if not all_docs:
        return

    # Round-robin embedders
    embedder_cycle = itertools.cycle(enumerate(embedder_pool))

    stats = {"success": 0, "failed": 0}
    stats_lock = asyncio.Lock()
    sem = asyncio.Semaphore(concurrency)
    start_time = time.monotonic()

    async def _process_one(doc: dict) -> None:
        doc_key = doc["doc_key"]
        async with sem:
            try:
                llm_result = json.loads(doc["llm_result"])
                parquet_meta = json.loads(doc["parquet_meta"])
                pdf_path = doc["pdf_path"]

                # Verify PDF still exists
                if not Path(pdf_path).exists():
                    state_db.mark_error(doc_key, f"PDF not found: {pdf_path}")
                    async with stats_lock:
                        stats["failed"] += 1
                    return

                # Create mock LLM with cached result
                mock_llm = BatchCachedLLM(result=llm_result)

                # Get embedder (round-robin)
                embed_idx, embedder = next(embedder_cycle)
                embed_limiter = (
                    embed_limiter_pool.get(api_keys[embed_idx]) if embed_limiter_pool else None
                )

                # Feed into existing pipeline — zero modifications
                async with async_session_factory() as db:
                    case_id = await asyncio.wait_for(
                        ingest_judgment(
                            pdf_path,
                            parquet_meta,
                            db=db,
                            llm=mock_llm,
                            embedder=embedder,
                            vector_store=vector_store,
                            graph_store=graph_store,
                            storage=storage,
                            embed_rate_limiter=embed_limiter,
                        ),
                        timeout=300.0,  # Shorter — no LLM wait
                    )

                if case_id:
                    state_db.update_doc_status(doc_key, "processed")
                    # Also mark in main ingest tracker for compatibility
                    await asyncio.to_thread(tracker.mark_success, doc_key, case_id)
                    async with stats_lock:
                        stats["success"] += 1
                else:
                    state_db.mark_error(doc_key, "ingest_judgment returned None")
                    async with stats_lock:
                        stats["failed"] += 1

                # Progress logging
                total = stats["success"] + stats["failed"]
                if total % 50 == 0:
                    elapsed = time.monotonic() - start_time
                    rate = stats["success"] / max(elapsed / 60, 0.01)
                    remaining = len(all_docs) - total
                    eta_min = remaining / max(rate, 0.01)
                    eta_str = (
                        f"{int(eta_min // 60)}h {int(eta_min % 60)}m"
                        if eta_min >= 60
                        else f"{int(eta_min)}m"
                    )
                    logger.info(
                        "Phase 3: %d/%d (%.1f%%) | %.1f/min | ETA: %s | %d failed",
                        stats["success"],
                        len(all_docs),
                        total / len(all_docs) * 100,
                        rate,
                        eta_str,
                        stats["failed"],
                    )

            except Exception as exc:
                logger.error("Phase 3 failed for %s: %s", doc_key, exc)
                state_db.mark_error(doc_key, f"process_failed: {exc}")
                async with stats_lock:
                    stats["failed"] += 1

    # Process all docs concurrently (bounded by semaphore)
    await asyncio.gather(*[_process_one(doc) for doc in all_docs])

    logger.info(
        "Phase 3 complete: %d success, %d failed out of %d",
        stats["success"],
        stats["failed"],
        len(all_docs),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch ingestion orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # submit
    p_submit = subparsers.add_parser("submit", help="Phase 1: Upload PDFs and submit batch jobs")
    p_submit.add_argument("--year-from", type=int, default=2015)
    p_submit.add_argument("--year-to", type=int, default=2023)
    p_submit.add_argument("--wave-size", type=int, default=WAVE_SIZE)
    p_submit.add_argument("--concurrency", type=int, default=10)
    p_submit.add_argument("--data-dir", type=str, default="data")

    # poll
    p_poll = subparsers.add_parser("poll", help="Phase 2: Poll batch jobs and collect results")
    p_poll.add_argument("--interval", type=int, default=60)

    # process
    p_process = subparsers.add_parser("process", help="Phase 3: Feed results into pipeline")
    p_process.add_argument("--year-from", type=int, default=2015)
    p_process.add_argument("--year-to", type=int, default=2023)
    p_process.add_argument("--concurrency", type=int, default=20)
    p_process.add_argument("--rpm-limit", type=int, default=0)

    args = parser.parse_args()

    api_keys = _build_key_pool()
    logger.info("Using %d Gemini API key(s)", len(api_keys))
    state_db = BatchStateDB()

    if args.command == "submit":
        for year in range(args.year_from, args.year_to + 1):
            asyncio.run(
                submit_year(
                    year,
                    api_keys,
                    state_db,
                    Path(args.data_dir),
                    wave_size=args.wave_size,
                    concurrency=args.concurrency,
                )
            )

    elif args.command == "poll":
        asyncio.run(poll_jobs(api_keys, state_db, interval=args.interval))

    elif args.command == "process":
        asyncio.run(
            process_completed(
                api_keys,
                state_db,
                year_from=args.year_from,
                year_to=args.year_to,
                concurrency=args.concurrency,
                rpm_limit=args.rpm_limit,
            )
        )


if __name__ == "__main__":
    main()
