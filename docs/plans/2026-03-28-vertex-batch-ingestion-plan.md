# Vertex AI Batch Ingestion Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build `backend/scripts/batch_ingest_vertex.py` — a 4-phase hybrid batch+online pipeline that ingests ~31K Supreme Court judgments via Vertex AI, producing identical output to the existing online pipeline at 50% LLM cost savings.

**Architecture:** Phase 1 extracts text from PDFs and uploads to GCS. Phase 2 submits a Vertex AI batch job for metadata extraction (50% discount). Phase 3 processes each case sequentially online: validate metadata → insert PG → chunk → contextual prefixes → embed → RAPTOR → Pinecone → Neo4j. Phase 4 runs quality checks. The script reuses all existing pipeline functions — no reimplementation.

**Tech Stack:** Python 3.12, google-genai SDK (Vertex AI), google-cloud-storage, existing pipeline modules (ingestion/pipeline.py, metadata.py, chunker.py, contextual_embeddings.py, section_summarizer.py, legal/extractor.py, legal/treatment.py)

---

## Task 1: Script Skeleton + CLI Arguments

**Files:**
- Create: `backend/scripts/batch_ingest_vertex.py`

**Step 1: Write the script skeleton with argparse**

```python
"""Vertex AI batch ingestion pipeline for Indian Supreme Court judgments.

4-phase hybrid pipeline:
  Phase 1: Extract text from PDFs, upload to GCS, build manifest
  Phase 2: Submit Vertex AI batch job for metadata extraction (50% discount)
  Phase 3: Process each case online (validate, PG, chunk, embed, Pinecone, Neo4j)
  Phase 4: Quality check on completed batch

Usage:
    python scripts/batch_ingest_vertex.py --year 2020 --limit 1000
    python scripts/batch_ingest_vertex.py --all --limit 1000
    python scripts/batch_ingest_vertex.py --resume batch_run_20260328_1400
    python scripts/batch_ingest_vertex.py --quality-check batch_run_20260328_1400
    python scripts/batch_ingest_vertex.py --year 2020 --limit 10 --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import signal
import sqlite3
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure the backend package is importable when running as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("batch_ingest_vertex")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
S3_BUCKET = "s3://indian-supreme-court-judgments"
GCS_BUCKET = "smriti-batch-ingestion"
BATCH_MODEL = "gemini-2.5-flash"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Vertex AI batch ingestion pipeline")
    p.add_argument("--year", type=int, help="Ingest a specific year")
    p.add_argument("--all", action="store_true", help="Ingest all remaining years (1950-2025)")
    p.add_argument("--limit", type=int, default=1000, help="Max cases per run (default: 1000)")
    p.add_argument("--resume", type=str, help="Resume Phase 3 from a previous batch run directory name")
    p.add_argument("--quality-check", type=str, dest="quality_check", help="Run quality check on a completed run")
    p.add_argument("--dry-run", action="store_true", help="Phase 1 only, no API calls")
    p.add_argument("--rpm-limit", type=int, default=30, help="Gemini RPM limit for online calls (default: 30)")
    p.add_argument("--concurrency", type=int, default=1, help="Concurrent cases in Phase 3 (default: 1)")
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    if args.quality_check:
        await phase4_quality_check(args.quality_check)
        return

    if args.resume:
        await phase3_online_processing(args.resume, args)
        return

    if not args.year and not args.all:
        logger.error("Must specify --year or --all")
        sys.exit(1)

    years = list(range(1950, 2026)) if args.all else [args.year]
    for year in years:
        run_id = f"batch_run_{datetime.now().strftime('%Y%m%d_%H%M')}_{year}"
        run_dir = Path(f"data/batch_runs/{run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)

        # Phase 1: Extract text, upload PDFs to GCS, build manifest
        manifest = await phase1_prepare(year, run_dir, args)
        if not manifest:
            logger.error("Phase 1 produced no cases for year %d", year)
            continue

        if args.dry_run:
            logger.info("DRY RUN: Phase 1 complete, %d cases in manifest", len(manifest))
            continue

        # Phase 2: Submit batch metadata extraction
        await phase2_batch_metadata(run_dir, manifest, args)

        # Phase 3: Online processing
        await phase3_online_processing(run_id, args)

        # Phase 4: Quality check
        await phase4_quality_check(run_id)


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Verify script runs with --help**

Run: `cd backend && python scripts/batch_ingest_vertex.py --help`
Expected: Help text printed, no import errors

**Step 3: Commit**

```bash
git add backend/scripts/batch_ingest_vertex.py
git commit -m "feat(batch): add script skeleton with CLI arguments"
```

---

## Task 2: Phase 1 — Text Extraction + GCS Upload

**Files:**
- Modify: `backend/scripts/batch_ingest_vertex.py`

**Step 1: Add S3 download + PDF extraction helpers**

Reuse `download_year_data`, `extract_tar`, `load_parquet_metadata`, `_match_pdf_to_metadata`, `_strip_language_suffix` from `ingest_s3.py`. Import them directly:

```python
from scripts.ingest_s3 import (
    download_year_data,
    extract_tar,
    load_parquet_metadata,
    _match_pdf_to_metadata,
    _strip_language_suffix,
    IngestTracker,
)
```

If circular import issues arise, copy the pure functions (`download_year_data`, `extract_tar`, `load_parquet_metadata`, `_match_pdf_to_metadata`, `_strip_language_suffix`) into a shared module `backend/scripts/_s3_helpers.py` and import from there in both scripts.

**Step 2: Add GCS upload function**

```python
from google.cloud import storage as gcs_storage

def _get_gcs_client() -> gcs_storage.Client:
    """Get GCS client using service account credentials."""
    from app.core.config import settings
    return gcs_storage.Client(project=settings.gemini_vertexai_project)


def _upload_pdf_to_gcs(local_path: Path, case_id: str) -> str:
    """Upload a PDF to GCS and return the gs:// URI."""
    client = _get_gcs_client()
    bucket = client.bucket(GCS_BUCKET)
    blob_name = f"pdfs/{case_id}.pdf"
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(str(local_path))
    return f"gs://{GCS_BUCKET}/{blob_name}"
```

**Step 3: Implement phase1_prepare**

```python
async def phase1_prepare(
    year: int, run_dir: Path, args: argparse.Namespace,
) -> list[dict]:
    """Phase 1: Extract text from PDFs, upload to GCS, build manifest.

    Returns list of manifest entries, each containing:
    - case_id, pdf_gcs_uri, extracted_text, text_hash, parquet_metadata, quality_tier
    """
    from app.core.ingestion.pdf import extract_and_score
    from app.db.postgres import async_session_factory
    from sqlalchemy import text as sa_text

    data_dir = Path("data/s3_cache")
    tar_path, parquet_path = download_year_data(year, data_dir)
    if tar_path is None:
        logger.error("Failed to download tar for year %d", year)
        return []

    extract_dir = data_dir / f"year={year}" / "extracted"
    pdf_paths = extract_tar(tar_path, extract_dir)

    metadata_map: dict[str, dict] = {}
    if parquet_path and parquet_path.exists():
        metadata_map = load_parquet_metadata(parquet_path)

    # Build stem index for O(1) matching
    stem_index: dict[str, str] = {}
    for key in metadata_map:
        stem = Path(str(key)).stem
        stem_index[stem] = key

    manifest: list[dict] = []
    skipped = {"no_text": 0, "duplicate": 0}

    for pdf_path in pdf_paths[:args.limit]:
        case_id = str(uuid.uuid4())
        parquet_meta = _match_pdf_to_metadata(pdf_path, metadata_map, stem_index)

        # 1a. Extract text
        try:
            quality = await extract_and_score(str(pdf_path))
        except Exception as exc:
            logger.warning("PDF extraction failed for %s: %s", pdf_path.name, exc)
            skipped["no_text"] += 1
            continue

        if not quality.text or quality.char_count < 50:
            logger.warning("Insufficient text from %s (%d chars)", pdf_path.name, quality.char_count)
            skipped["no_text"] += 1
            continue

        full_text = quality.text

        # 1b. Dedup check via text_hash
        normalized = re.sub(r'\s+', ' ', full_text.strip().lower())
        text_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()

        async with async_session_factory() as db:
            existing = await db.execute(
                sa_text("SELECT id, chunk_count FROM cases WHERE text_hash = :hash"),
                {"hash": text_hash},
            )
            row = existing.fetchone()
            if row and row[1] and row[1] > 0:
                logger.info("Duplicate (text_hash) %s, skipping", pdf_path.name)
                skipped["duplicate"] += 1
                continue

        # 1c. Upload PDF to GCS (skip in dry-run)
        pdf_gcs_uri = ""
        if not args.dry_run:
            try:
                pdf_gcs_uri = _upload_pdf_to_gcs(pdf_path, case_id)
            except Exception as exc:
                logger.warning("GCS upload failed for %s: %s", pdf_path.name, exc)
                # Still include in manifest — Phase 2 will use text fallback
                pdf_gcs_uri = ""

        manifest.append({
            "case_id": case_id,
            "pdf_path": str(pdf_path),
            "pdf_gcs_uri": pdf_gcs_uri,
            "extracted_text": full_text,
            "text_hash": text_hash,
            "parquet_metadata": parquet_meta,
            "quality_tier": quality.tier,
            "char_count": quality.char_count,
            "page_map": quality.page_map,
        })

    # Save manifest
    manifest_path = run_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, default=str)

    logger.info(
        "Phase 1 complete: %d cases prepared, %d skipped (no_text=%d, duplicate=%d)",
        len(manifest), sum(skipped.values()), skipped["no_text"], skipped["duplicate"],
    )
    return manifest
```

**Step 4: Test Phase 1 with dry run**

Run: `cd backend && python scripts/batch_ingest_vertex.py --year 2024 --limit 5 --dry-run`
Expected: Downloads tar/parquet for 2024, extracts PDFs, prints "DRY RUN: Phase 1 complete, N cases in manifest"

**Step 5: Commit**

```bash
git add backend/scripts/batch_ingest_vertex.py
git commit -m "feat(batch): implement Phase 1 — text extraction + GCS upload"
```

---

## Task 3: Phase 2 — Batch Metadata Extraction via Vertex AI

**Files:**
- Modify: `backend/scripts/batch_ingest_vertex.py`

**Step 1: Add JSONL builder for batch input**

```python
from app.core.legal.prompts import (
    METADATA_EXTRACTION_SYSTEM,
    METADATA_EXTRACTION_USER,
    METADATA_OUTPUT_SCHEMA,
)


def _build_batch_jsonl(manifest: list[dict], output_path: Path) -> int:
    """Build JSONL file for Vertex AI batch prediction.

    Each line is one request with PDF multimodal (if GCS URI available)
    or text fallback.

    Returns number of requests written.
    """
    count = 0
    with open(output_path, "w") as f:
        for entry in manifest:
            # Build content parts
            parts: list[dict] = []

            if entry.get("pdf_gcs_uri"):
                # PDF multimodal — preferred for old/scanned PDFs
                parts.append({
                    "fileData": {
                        "fileUri": entry["pdf_gcs_uri"],
                        "mimeType": "application/pdf",
                    }
                })
                parts.append({"text": METADATA_EXTRACTION_USER})
            else:
                # Text fallback — use head+tail truncation like online pipeline
                text = entry["extracted_text"]
                head_chars, tail_chars = 30_000, 20_000
                if len(text) > head_chars + tail_chars:
                    text = (
                        text[:head_chars]
                        + "\n\n[...middle section truncated for length...]\n\n"
                        + text[-tail_chars:]
                    )
                parts.append({"text": f"{text}\n\n{METADATA_EXTRACTION_USER}"})

            request = {
                "request": {
                    "model": BATCH_MODEL,
                    "contents": [{"role": "user", "parts": parts}],
                    "systemInstruction": {
                        "parts": [{"text": METADATA_EXTRACTION_SYSTEM}]
                    },
                    "generationConfig": {
                        "temperature": 0.1,
                        "responseMimeType": "application/json",
                        "responseSchema": METADATA_OUTPUT_SCHEMA,
                    },
                }
            }
            f.write(json.dumps(request) + "\n")
            count += 1

    return count
```

**Step 2: Add batch job submission + polling**

```python
from google import genai


def _get_vertex_client() -> genai.Client:
    """Get Vertex AI genai client."""
    from app.core.config import settings
    return genai.Client(
        vertexai=True,
        project=settings.gemini_vertexai_project,
        location=settings.gemini_vertexai_location,
    )


async def phase2_batch_metadata(
    run_dir: Path, manifest: list[dict], args: argparse.Namespace,
) -> None:
    """Phase 2: Submit batch metadata extraction job and wait for completion."""
    from google.cloud import storage as gcs_storage
    from app.core.config import settings

    # 2a. Build JSONL
    jsonl_path = run_dir / "batch_input.jsonl"
    count = _build_batch_jsonl(manifest, jsonl_path)
    logger.info("Built JSONL with %d requests", count)

    # 2b. Upload JSONL to GCS
    gcs_client = _get_gcs_client()
    bucket = gcs_client.bucket(GCS_BUCKET)
    run_name = run_dir.name
    input_blob = bucket.blob(f"batch-jobs/{run_name}/input.jsonl")
    input_blob.upload_from_filename(str(jsonl_path))
    input_uri = f"gs://{GCS_BUCKET}/batch-jobs/{run_name}/input.jsonl"
    output_uri = f"gs://{GCS_BUCKET}/batch-jobs/{run_name}/output/"
    logger.info("Uploaded JSONL to %s", input_uri)

    # 2c. Submit batch job
    client = _get_vertex_client()
    batch_job = client.batches.create(
        model=BATCH_MODEL,
        src=input_uri,
        dest=output_uri,
        config={
            "display_name": f"smriti-{run_name}",
        },
    )
    batch_name = batch_job.name
    logger.info("Batch job submitted: %s", batch_name)

    # Save batch job info for resume
    batch_info = {
        "batch_name": batch_name,
        "input_uri": input_uri,
        "output_uri": output_uri,
        "case_count": count,
        "submitted_at": datetime.now().isoformat(),
    }
    with open(run_dir / "batch_info.json", "w") as f:
        json.dump(batch_info, f, indent=2)

    # 2d. Poll for completion (check every 2 min)
    logger.info("Waiting for batch job to complete (polling every 2 min)...")
    while True:
        batch = client.batches.get(name=batch_name)
        state_str = str(batch.state)

        if "SUCCEEDED" in state_str or "COMPLETED" in state_str:
            logger.info("Batch job SUCCEEDED!")
            break
        elif "FAILED" in state_str or "CANCELLED" in state_str:
            logger.error("Batch job FAILED: %s", batch.state)
            if hasattr(batch, "error"):
                logger.error("Error: %s", batch.error)
            raise RuntimeError(f"Batch job failed: {batch.state}")
        else:
            logger.info("Batch status: %s — waiting 2 min...", batch.state)
            await asyncio.sleep(120)

    # 2e. Download results
    output_blobs = list(bucket.list_blobs(prefix=f"batch-jobs/{run_name}/output/"))
    results: list[dict] = []
    for blob in output_blobs:
        if blob.name.endswith(".jsonl"):
            content = blob.download_as_text()
            for line in content.strip().split("\n"):
                if line.strip():
                    results.append(json.loads(line))

    # 2f. Save results
    results_path = run_dir / "metadata_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, default=str)

    logger.info("Phase 2 complete: %d metadata results downloaded", len(results))

    # Quality gate: abort if >10% failures
    failed_count = sum(
        1 for r in results
        if not r.get("response", {}).get("candidates")
    )
    if count > 0 and failed_count / count > 0.10:
        raise RuntimeError(
            f"Quality gate FAILED: {failed_count}/{count} cases ({failed_count/count:.0%}) "
            f"have no metadata. Check batch job output."
        )
```

**Step 3: Test Phase 2 with a small batch (2-3 cases)**

Run: `cd backend && python scripts/batch_ingest_vertex.py --year 2024 --limit 3`
Expected: Phase 1 extracts 3 PDFs, Phase 2 submits batch job, polls until complete, downloads results. Watch for the "Batch job SUCCEEDED!" log line.

**Step 4: Commit**

```bash
git add backend/scripts/batch_ingest_vertex.py
git commit -m "feat(batch): implement Phase 2 — Vertex AI batch metadata extraction"
```

---

## Task 4: Phase 3 — Parse Batch Results + Metadata Validation

**Files:**
- Modify: `backend/scripts/batch_ingest_vertex.py`

**Step 1: Add batch result parser**

This function parses the Vertex AI batch output JSONL and maps results back to manifest entries. The batch output lines correspond 1:1 with the input JSONL lines (same order).

```python
from app.core.ingestion.metadata import (
    CaseMetadata,
    compute_extraction_confidence,
    cross_validate_propositions,
    merge_metadata,
    validate_cross_fields,
    validate_parquet_data,
    validate_with_regex,
)
from app.core.legal.extractor import (
    extract_acts_cited,
    extract_citations,
    normalize_acts_cited_list,
)
from app.core.legal.statute_enrichment import enrich_statute_cross_references


def _parse_batch_result(batch_item: dict) -> dict | None:
    """Parse a single batch result into a metadata dict.

    Returns the parsed JSON dict, or None if parsing fails.
    """
    try:
        response = batch_item.get("response", {})
        candidates = response.get("candidates", [])
        if not candidates:
            return None
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        return json.loads(text)
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning("Failed to parse batch result: %s", exc)
        return None


def _batch_dict_to_case_metadata(raw: dict) -> CaseMetadata:
    """Convert a raw batch metadata dict to a CaseMetadata dataclass.

    Matches the same field mapping that extract_metadata_llm() returns.
    """
    from app.core.ingestion.metadata import _parse_judge_names

    return CaseMetadata(
        title=raw.get("title"),
        citation=raw.get("citation"),
        court=raw.get("court"),
        judge=_parse_judge_names(raw.get("judge")),
        author_judge=raw.get("author_judge"),
        year=raw.get("year"),
        decision_date=raw.get("decision_date"),
        case_type=raw.get("case_type"),
        case_number=raw.get("case_number"),
        bench_type=raw.get("bench_type"),
        coram_size=raw.get("coram_size"),
        jurisdiction=raw.get("jurisdiction"),
        petitioner=raw.get("petitioner"),
        respondent=raw.get("respondent"),
        petitioner_type=raw.get("petitioner_type"),
        respondent_type=raw.get("respondent_type"),
        is_pil=raw.get("is_pil"),
        ratio_decidendi=raw.get("ratio_decidendi"),
        acts_cited=raw.get("acts_cited"),
        cases_cited=raw.get("cases_cited"),
        keywords=raw.get("keywords"),
        disposal_nature=raw.get("disposal_nature"),
        is_reportable=raw.get("is_reportable"),
        headnotes=json.dumps(raw["headnotes"]) if raw.get("headnotes") else None,
        outcome_summary=raw.get("outcome_summary"),
        lower_court=raw.get("lower_court"),
        lower_court_case_number=raw.get("lower_court_case_number"),
        appeal_from=raw.get("appeal_from"),
        opinion_type=raw.get("opinion_type"),
        dissenting_judges=raw.get("dissenting_judges"),
        concurring_judges=raw.get("concurring_judges"),
        split_ratio=raw.get("split_ratio"),
        companion_cases=raw.get("companion_cases"),
        # V2 fields
        arguments_raised=raw.get("arguments_raised"),
        relief_granted=raw.get("relief_granted"),
        relief_sought=raw.get("relief_sought"),
        sentence_details=raw.get("sentence_details"),
        damages_awarded=raw.get("damages_awarded"),
        judicial_tone=raw.get("judicial_tone"),
        key_observations=raw.get("key_observations"),
        hearing_count=raw.get("hearing_count"),
        citation_treatments=raw.get("citation_treatments"),
        distinguished_cases=raw.get("distinguished_cases"),
        overruled_cases=raw.get("overruled_cases"),
        legal_principles_applied=raw.get("legal_principles_applied"),
        procedural_history=raw.get("procedural_history"),
        interim_orders=raw.get("interim_orders"),
        filing_date=raw.get("filing_date"),
        urgency_indicators=raw.get("urgency_indicators"),
        party_counsel=raw.get("party_counsel"),
        issue_classification=raw.get("issue_classification"),
        fact_pattern_tags=raw.get("fact_pattern_tags"),
        operative_order=raw.get("operative_order"),
        conditions_imposed=raw.get("conditions_imposed"),
        costs_awarded=raw.get("costs_awarded"),
        # V3 fields
        legal_propositions=raw.get("legal_propositions"),
        statute_sections_interpreted=raw.get("statute_sections_interpreted"),
        fact_pattern_summary=raw.get("fact_pattern_summary"),
    )
```

**Step 2: Add metadata validation function (reuses existing pipeline)**

```python
def _validate_and_enrich_metadata(
    llm_meta: CaseMetadata,
    parquet_meta: dict,
    full_text: str,
) -> tuple[CaseMetadata, dict[str, str], float]:
    """Validate and enrich metadata — same logic as ingest_judgment steps 2-3.

    Returns (metadata, provenance, extraction_confidence).
    """
    validated_parquet = validate_parquet_data(parquet_meta)
    metadata, provenance = merge_metadata(validated_parquet, llm_meta)

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
        provenance["acts_cited"] = "llm+regex"

    if metadata.acts_cited:
        metadata.acts_cited = normalize_acts_cited_list(metadata.acts_cited)
        provenance["acts_cited"] = provenance.get("acts_cited", "llm") + "+normalized"

    if metadata.acts_cited:
        metadata.acts_cited = enrich_statute_cross_references(metadata.acts_cited)
        provenance["acts_cited"] = provenance.get("acts_cited", "llm") + "+enriched"

    # Supplement cases_cited with regex
    regex_citations = extract_citations(full_text)
    if regex_citations:
        llm_cases = set(metadata.cases_cited or [])
        for cit in regex_citations:
            llm_cases.add(cit.raw_text)
        metadata.cases_cited = sorted(llm_cases)
        provenance["cases_cited"] = "llm+regex"

    extraction_confidence = compute_extraction_confidence(metadata)
    return metadata, provenance, extraction_confidence
```

**Step 3: Commit**

```bash
git add backend/scripts/batch_ingest_vertex.py
git commit -m "feat(batch): add batch result parser and metadata validation"
```

---

## Task 5: Phase 3 — Full Online Processing Per Case

**Files:**
- Modify: `backend/scripts/batch_ingest_vertex.py`

This is the largest task. Phase 3 processes each case sequentially, reusing existing pipeline functions for: PG insert, chunking, contextual prefixes, embedding, RAPTOR summaries, Pinecone upsert, and Neo4j graph.

**Step 1: Add the per-case processing function**

```python
from app.core.ingestion.chunker import chunk_judgment, detect_judgment_sections
from app.core.ingestion.pipeline import (
    _build_citation_graph,
    _embed_chunks,
    _insert_case,
    _link_citation_equivalents,
    _extract_citation_equivalents,
    _persist_sections,
    _persist_statute_interpretations,
    _upsert_proposition_vectors,
    _upsert_vectors,
)
from app.core.ingestion.rate_limiter import AsyncRateLimiter
from app.core.interfaces.embedder import EmbeddingProvider
from app.core.interfaces.graph_store import GraphStore
from app.core.interfaces.llm import LLMProvider
from app.core.interfaces.vector_store import VectorStore
from app.db.postgres import async_session_factory
from sqlalchemy import text as sa_text


async def _process_single_case(
    entry: dict,
    batch_metadata: dict | None,
    *,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    graph_store: GraphStore,
    llm_rate_limiter: AsyncRateLimiter | None = None,
    embed_rate_limiter: AsyncRateLimiter | None = None,
) -> str | None:
    """Process a single case through the full online pipeline (steps A-H).

    Returns case_id on success, None on failure.
    """
    case_id = entry["case_id"]
    full_text = entry["extracted_text"]
    parquet_meta = entry.get("parquet_metadata", {})
    page_map = entry.get("page_map")
    text_hash = entry["text_hash"]

    # A. Parse + validate batch metadata
    if batch_metadata is None:
        logger.error("No batch metadata for case_id=%s, skipping", case_id)
        return None

    llm_meta = _batch_dict_to_case_metadata(batch_metadata)
    metadata, provenance, extraction_confidence = _validate_and_enrich_metadata(
        llm_meta, parquet_meta, full_text,
    )

    # B. Insert into PostgreSQL
    async with async_session_factory() as db:
        case_id, already_ingested = await _insert_case(
            db, case_id, metadata, full_text,
            entry.get("pdf_gcs_uri", entry.get("pdf_path", "")),
            parquet_meta,
            provenance=provenance,
            text_hash=text_hash,
            extraction_confidence=extraction_confidence,
            page_map=page_map,
        )

        if already_ingested:
            logger.info("Case %s already fully ingested, skipping", metadata.citation)
            return case_id

        # Mark as processing
        async with db.begin_nested():
            await db.execute(
                sa_text("UPDATE cases SET ingestion_status = 'processing', updated_at = NOW() WHERE id = :id"),
                {"id": case_id},
            )

        db_committed = False
        vectors_upserted = False

        try:
            # C. Detect sections + chunk
            sections = detect_judgment_sections(full_text)
            chunks = chunk_judgment(full_text, sections, case_id=case_id)
            logger.info("case_id=%s: %d sections, %d chunks", case_id, len(sections), len(chunks))

            # C2. Persist sections + citation equivalents
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
                from app.core.ingestion.pipeline import _persist_citation_equivalents
                await _persist_citation_equivalents(citation_equivalents, db)

            # D. Contextual prefixes (online LLM)
            from app.core.ingestion.contextual_embeddings import batch_contextualize_chunks
            chunk_dicts = [{"text": c.text, "section_type": c.section_type} for c in chunks]
            doc_meta = {
                "title": metadata.title or "",
                "citation": metadata.citation or "",
                "court": metadata.court or "",
                "year": metadata.year or 0,
            }
            contextualized = await batch_contextualize_chunks(
                chunk_dicts, doc_meta, llm, document_type="case_law",
                rate_limiter=llm_rate_limiter,
            )
            contextualized_texts = [c["contextualized_text"] for c in contextualized]

            # E. Embed chunks (online)
            embeddings = await asyncio.wait_for(
                _embed_chunks(chunks, embedder, rate_limiter=embed_rate_limiter,
                              texts_override=contextualized_texts),
                timeout=300.0,
            )
            if len(embeddings) != len(chunks):
                raise RuntimeError(
                    f"Embedding count mismatch: {len(embeddings)} vs {len(chunks)} chunks"
                )

            # F. Upsert chunk vectors to Pinecone
            await _upsert_vectors(
                case_id, chunks, embeddings, metadata, vector_store,
                page_map=page_map, full_text=full_text,
            )
            vectors_upserted = True

            # F2. Proposition/ratio/headnote vectors
            new_vector_ids = [f"{case_id}_{c.chunk_index}" for c in chunks]
            proposition_vectors_failed = False
            try:
                prop_count, prop_ids = await _upsert_proposition_vectors(
                    case_id, metadata, embedder, vector_store,
                    rate_limiter=embed_rate_limiter,
                )
                new_vector_ids.extend(prop_ids)
                if prop_count:
                    logger.info("Created %d proposition vectors for %s", prop_count, case_id)
            except Exception as exc:
                logger.warning("Proposition vectors failed for %s: %s", case_id, exc)
                proposition_vectors_failed = True

            # F3. Stale vector cleanup
            try:
                await vector_store.delete_by_metadata(
                    {"case_id": case_id},
                    exclude_ids=new_vector_ids,
                )
            except Exception:
                logger.warning("Stale vector cleanup failed for %s", case_id)

            # G. RAPTOR section summaries (online LLM)
            try:
                from app.core.ingestion.section_summarizer import (
                    build_pinecone_summary_vectors,
                    generate_section_summaries,
                )
                section_dicts = [
                    {"section_type": s.type, "content": s.text}
                    for s in sections
                ]
                summaries = await generate_section_summaries(str(case_id), section_dicts, llm)
                if summaries:
                    summary_texts = [s["summary_text"] for s in summaries]
                    if embed_rate_limiter:
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
                    logger.info("case_id=%s: %d RAPTOR summaries stored", case_id, len(summaries))
            except Exception as raptor_exc:
                logger.warning("RAPTOR failed for %s: %s", case_id, raptor_exc)

            # H. Update chunk_count + finalize
            _REVIEW_THRESHOLD = 0.5
            if extraction_confidence < _REVIEW_THRESHOLD or proposition_vectors_failed:
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

            await db.commit()
            db_committed = True

            # I. Citation graph (non-critical)
            try:
                await asyncio.wait_for(
                    _build_citation_graph(case_id, metadata, full_text, graph_store),
                    timeout=60.0,
                )
                if citation_equivalents:
                    await _link_citation_equivalents(
                        case_id, metadata.citation, citation_equivalents, graph_store,
                    )
            except Exception as graph_exc:
                logger.warning("Citation graph failed for %s: %s", case_id, graph_exc)

        except Exception as exc:
            logger.error("Pipeline failed for case_id=%s: %s", case_id, exc)
            if not db_committed:
                try:
                    await db.rollback()
                except Exception:
                    pass
                if vectors_upserted:
                    try:
                        await vector_store.delete_by_metadata({"case_id": case_id})
                    except Exception:
                        pass
            return None

    logger.info("Case %s ingested successfully (chunks=%d)", case_id, len(chunks))
    return case_id
```

**Step 2: Add the Phase 3 orchestrator**

```python
async def phase3_online_processing(
    run_id: str, args: argparse.Namespace,
) -> None:
    """Phase 3: Process each case through the full online pipeline."""
    from app.core.config import settings
    from app.core.dependencies import get_graph_store, get_vector_store
    from app.core.providers.embeddings.gemini import GeminiEmbedder
    from app.core.providers.llm.gemini import GeminiLLM
    from app.core.ingestion.rate_limiter import AsyncRateLimiter

    run_dir = Path(f"data/batch_runs/{run_id}")
    manifest_path = run_dir / "manifest.json"
    results_path = run_dir / "metadata_results.json"

    if not manifest_path.exists() or not results_path.exists():
        logger.error("Missing manifest.json or metadata_results.json in %s", run_dir)
        return

    with open(manifest_path) as f:
        manifest = json.load(f)
    with open(results_path) as f:
        batch_results = json.load(f)

    logger.info("Phase 3: %d cases in manifest, %d batch results", len(manifest), len(batch_results))

    # Initialize providers (Vertex AI)
    llm = GeminiLLM(use_vertexai=True, model=settings.gemini_flash_model)
    embedder = GeminiEmbedder(use_vertexai=True)
    vector_store = get_vector_store()
    graph_store = get_graph_store()

    # Rate limiters
    llm_limiter = AsyncRateLimiter(rpm=args.rpm_limit) if args.rpm_limit > 0 else None
    embed_limiter = AsyncRateLimiter(rpm=args.rpm_limit * 5) if args.rpm_limit > 0 else None

    # Progress tracking
    progress_path = run_dir / "progress.json"
    completed_ids: set[str] = set()
    if progress_path.exists():
        with open(progress_path) as f:
            progress = json.load(f)
            completed_ids = set(progress.get("completed", []))
        logger.info("Resuming: %d cases already completed", len(completed_ids))

    stats = {"success": 0, "failed": 0, "skipped": 0}
    start_time = time.monotonic()

    for i, entry in enumerate(manifest):
        case_id = entry["case_id"]

        if case_id in completed_ids:
            stats["skipped"] += 1
            continue

        # Match batch result by index (1:1 correspondence)
        batch_metadata = None
        if i < len(batch_results):
            batch_metadata = _parse_batch_result(batch_results[i])

        logger.info(
            "[%d/%d] Processing case_id=%s (%s)",
            i + 1, len(manifest), case_id,
            entry.get("parquet_metadata", {}).get("title", "unknown")[:60],
        )

        try:
            result = await _process_single_case(
                entry, batch_metadata,
                llm=llm, embedder=embedder,
                vector_store=vector_store, graph_store=graph_store,
                llm_rate_limiter=llm_limiter,
                embed_rate_limiter=embed_limiter,
            )
            if result:
                stats["success"] += 1
                completed_ids.add(case_id)
            else:
                stats["failed"] += 1
        except Exception as exc:
            logger.error("Unhandled error for case_id=%s: %s", case_id, exc)
            stats["failed"] += 1

        # Save progress after each case
        with open(progress_path, "w") as f:
            json.dump({
                "completed": list(completed_ids),
                "stats": stats,
                "last_updated": datetime.now().isoformat(),
            }, f)

        # ETA logging every 10 cases
        if (i + 1) % 10 == 0:
            elapsed = time.monotonic() - start_time
            processed = stats["success"] + stats["failed"]
            remaining = len(manifest) - len(completed_ids)
            if processed > 0:
                eta_secs = (elapsed / processed) * remaining
                logger.info(
                    "Progress: %d/%d done, %d failed, ETA: %.0f min",
                    len(completed_ids), len(manifest), stats["failed"], eta_secs / 60,
                )

    logger.info(
        "Phase 3 complete: %d success, %d failed, %d skipped",
        stats["success"], stats["failed"], stats["skipped"],
    )
```

**Step 3: Commit**

```bash
git add backend/scripts/batch_ingest_vertex.py
git commit -m "feat(batch): implement Phase 3 — full online processing per case"
```

---

## Task 6: Phase 4 — Quality Check

**Files:**
- Modify: `backend/scripts/batch_ingest_vertex.py`

**Step 1: Implement quality check**

```python
async def phase4_quality_check(run_id: str) -> None:
    """Phase 4: Quality check on a completed batch run.

    Samples 10 random cases and verifies:
    - All 5 vector types present in Pinecone (chunk, proposition, ratio, headnote, summary)
    - chunk_count matches PG
    - Key PG fields non-null (title, citation, court, year, judge, ratio_decidendi)
    - extraction_confidence score
    """
    from app.core.dependencies import get_vector_store
    from app.db.postgres import async_session_factory
    import random

    run_dir = Path(f"data/batch_runs/{run_id}")
    progress_path = run_dir / "progress.json"

    if not progress_path.exists():
        logger.error("No progress.json found in %s", run_dir)
        return

    with open(progress_path) as f:
        progress = json.load(f)

    completed_ids = progress.get("completed", [])
    if not completed_ids:
        logger.error("No completed cases found")
        return

    sample_size = min(10, len(completed_ids))
    sample_ids = random.sample(completed_ids, sample_size)

    vector_store = get_vector_store()
    flagged: list[dict] = []

    REQUIRED_VECTOR_TYPES = {"chunk", "proposition", "ratio", "headnote", "summary"}
    REQUIRED_PG_FIELDS = ["title", "citation", "court", "year", "judge", "ratio_decidendi"]

    for case_id in sample_ids:
        issues: list[str] = []

        # Check Pinecone vectors
        try:
            # Query all vectors for this case_id
            vectors = await vector_store.query_by_metadata(
                {"case_id": case_id}, top_k=200,
            )
            found_types = set()
            for v in vectors:
                vtype = v.get("metadata", {}).get("vector_type", "chunk")
                found_types.add(vtype)

            missing_types = REQUIRED_VECTOR_TYPES - found_types
            if missing_types:
                issues.append(f"missing_vector_types: {missing_types}")

            chunk_vectors = [v for v in vectors if v.get("metadata", {}).get("vector_type", "chunk") == "chunk"]
        except Exception as exc:
            issues.append(f"pinecone_query_failed: {exc}")
            chunk_vectors = []

        # Check PostgreSQL
        async with async_session_factory() as db:
            result = await db.execute(
                sa_text(
                    "SELECT title, citation, court, year, judge, ratio_decidendi, "
                    "chunk_count, extraction_confidence, ingestion_status "
                    "FROM cases WHERE id = :id"
                ),
                {"id": case_id},
            )
            row = result.fetchone()

            if not row:
                issues.append("case_not_found_in_pg")
            else:
                # Check required fields
                for i, field in enumerate(REQUIRED_PG_FIELDS):
                    if row[i] is None:
                        issues.append(f"null_field: {field}")

                pg_chunk_count = row[6]  # chunk_count
                confidence = row[7]  # extraction_confidence
                status = row[8]  # ingestion_status

                if pg_chunk_count == 0:
                    issues.append("chunk_count=0")
                elif chunk_vectors and pg_chunk_count != len(chunk_vectors):
                    issues.append(f"chunk_mismatch: pg={pg_chunk_count}, pinecone={len(chunk_vectors)}")

                if confidence is not None and confidence < 0.5:
                    issues.append(f"low_confidence: {confidence:.2f}")

                logger.info(
                    "  %s: status=%s, chunks=%s, confidence=%.2f, vectors=%d types %s",
                    case_id[:8], status, pg_chunk_count,
                    confidence or 0, len(found_types) if 'found_types' in dir() else 0,
                    "OK" if not issues else f"ISSUES: {issues}",
                )

        if issues:
            flagged.append({"case_id": case_id, "issues": issues})

    # Summary
    print(f"\n{'='*60}")
    print(f"QUALITY CHECK: {run_id}")
    print(f"{'='*60}")
    print(f"Total completed: {len(completed_ids)}")
    print(f"Sampled: {sample_size}")
    print(f"Flagged: {len(flagged)}")

    if flagged:
        print(f"\nFLAGGED CASES:")
        for f_case in flagged:
            print(f"  {f_case['case_id'][:8]}: {', '.join(f_case['issues'])}")
    else:
        print("\nAll sampled cases PASSED quality check!")

    # Save report
    report_path = run_dir / "quality_report.json"
    with open(report_path, "w") as f:
        json.dump({
            "run_id": run_id,
            "total_completed": len(completed_ids),
            "sampled": sample_size,
            "flagged_count": len(flagged),
            "flagged": flagged,
            "checked_at": datetime.now().isoformat(),
        }, f, indent=2)

    print(f"\nReport saved to {report_path}")
```

**Step 2: Commit**

```bash
git add backend/scripts/batch_ingest_vertex.py
git commit -m "feat(batch): implement Phase 4 — quality check"
```

---

## Task 7: FTS Trigger Management + Graceful Shutdown

**Files:**
- Modify: `backend/scripts/batch_ingest_vertex.py`

**Step 1: Add FTS trigger disable/enable (reuse from ingest_s3.py)**

Import the FTS management functions from `ingest_s3.py`:

```python
from scripts.ingest_s3 import (
    _disable_fts_trigger,
    _enable_fts_trigger,
    _rebuild_fts_vectors,
)
```

**Step 2: Add graceful shutdown handler**

```python
_shutdown_event = asyncio.Event()


def _setup_shutdown_handler() -> None:
    """Install signal handlers for graceful shutdown."""
    loop = asyncio.get_event_loop()

    def _handler(sig: int, frame: object) -> None:
        logger.warning("Received signal %s, initiating graceful shutdown...", signal.Signals(sig).name)
        if loop.is_running():
            loop.call_soon_threadsafe(_shutdown_event.set)
        else:
            _shutdown_event.set()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)
```

**Step 3: Wire FTS + shutdown into main()**

Update the `main()` function to disable FTS trigger before Phase 3 and re-enable + rebuild after:

```python
async def main() -> None:
    args = parse_args()
    _setup_shutdown_handler()

    if args.quality_check:
        await phase4_quality_check(args.quality_check)
        return

    if args.resume:
        await _disable_fts_trigger()
        try:
            await phase3_online_processing(args.resume, args)
        finally:
            await _enable_fts_trigger()
            await _rebuild_fts_vectors()
        await phase4_quality_check(args.resume)
        return

    # ... rest of main unchanged, but wrap Phase 3 in FTS disable/enable:
    # await _disable_fts_trigger()
    # try:
    #     await phase3_online_processing(run_id, args)
    # finally:
    #     await _enable_fts_trigger()
    #     await _rebuild_fts_vectors()
```

Also add shutdown check in the Phase 3 processing loop — check `_shutdown_event.is_set()` before processing each case and break early if set, saving progress.

**Step 4: Commit**

```bash
git add backend/scripts/batch_ingest_vertex.py
git commit -m "feat(batch): add FTS trigger management and graceful shutdown"
```

---

## Task 8: GCP Credits Exhaustion Detection

**Files:**
- Modify: `backend/scripts/batch_ingest_vertex.py`

**Step 1: Add 403 detection in Phase 3**

Wrap the per-case processing in a try/except that catches 403 BILLING_DISABLED errors from Vertex AI:

```python
# Inside the Phase 3 loop, after the process call:
except Exception as exc:
    error_str = str(exc)
    if "403" in error_str and ("BILLING" in error_str.upper() or "PERMISSION" in error_str.upper()):
        logger.critical(
            "GCP credits likely exhausted (403 error). "
            "Pausing pipeline. Switch to a new GCP account and resume with:\n"
            "  python scripts/batch_ingest_vertex.py --resume %s",
            run_id,
        )
        break  # Stop processing, progress is saved
    logger.error("Unhandled error for case_id=%s: %s", case_id, exc)
    stats["failed"] += 1
```

**Step 2: Commit**

```bash
git add backend/scripts/batch_ingest_vertex.py
git commit -m "feat(batch): detect GCP credit exhaustion and pause gracefully"
```

---

## Task 9: End-to-End Test (3 Cases)

**Files:**
- No new files

**Step 1: Run a 3-case end-to-end test**

Run: `cd backend && python scripts/batch_ingest_vertex.py --year 2024 --limit 3 --rpm-limit 15`

Expected behavior:
1. Phase 1: Downloads 2024 tar, extracts 3 PDFs, uploads to GCS, builds manifest
2. Phase 2: Submits batch job, polls until complete (~5-30 min), downloads results
3. Phase 3: Processes 3 cases (validate → PG → chunk → contextual → embed → RAPTOR → Pinecone → Neo4j)
4. Phase 4: Samples up to 3 cases, checks vector types and PG fields

**Step 2: Verify in PostgreSQL**

Run: `cd backend && python -c "
import asyncio
from app.db.postgres import async_session_factory
from sqlalchemy import text
async def check():
    async with async_session_factory() as db:
        r = await db.execute(text(
            \"SELECT id, title, citation, chunk_count, ingestion_status, extraction_confidence \"
            \"FROM cases WHERE source_dataset = 'aws_open_data_sc' \"
            \"ORDER BY created_at DESC LIMIT 5\"
        ))
        for row in r.fetchall():
            print(row)
asyncio.run(check())
"`

Expected: 3 new cases with `ingestion_status='complete'`, non-zero `chunk_count`, `extraction_confidence > 0.5`

**Step 3: Verify in Pinecone**

Check that all 5 vector types exist for one of the ingested case_ids. Use the quality check:

Run: `cd backend && python scripts/batch_ingest_vertex.py --quality-check <run_id>`

Expected: "All sampled cases PASSED quality check!"

**Step 4: Test resume capability**

Run the same command again — it should skip all 3 already-completed cases:

Run: `cd backend && python scripts/batch_ingest_vertex.py --resume <run_id>`

Expected: "Resuming: 3 cases already completed" → "Phase 3 complete: 0 success, 0 failed, 3 skipped"

**Step 5: Commit**

```bash
git add backend/scripts/batch_ingest_vertex.py
git commit -m "feat(batch): verified end-to-end pipeline with 3 cases"
```

---

## Task 10: Update Memory + Clean Up

**Files:**
- Modify: `C:\Users\yadav\.claude\projects\d--Startup-Smriti\memory\MEMORY.md`
- Modify: `C:\Users\yadav\.claude\projects\d--Startup-Smriti\memory\ingestion-details.md`

**Step 1: Update memory with batch pipeline info**

Add to MEMORY.md:
- Batch pipeline script location: `backend/scripts/batch_ingest_vertex.py`
- 4-phase architecture: prepare → batch metadata → online processing → quality check
- Resume capability via `--resume <run_id>`
- Vertex AI batch uses `gemini-2.5-flash` (not preview models)

**Step 2: Clean up test batch artifacts on GCS**

Run: `gsutil rm -r gs://smriti-batch-ingestion/test/ gs://smriti-batch-ingestion/ab-test/`

**Step 3: Commit**

```bash
git commit -m "docs: update memory with batch pipeline details"
```

---

## Dependency Map

```
Task 1 (skeleton) → Task 2 (Phase 1) → Task 3 (Phase 2) → Task 4 (result parser)
                                                                     ↓
Task 7 (FTS + shutdown) ←── Task 5 (Phase 3) ←─────────────────────┘
         ↓
Task 8 (credits detection)
         ↓
Task 6 (Phase 4) → Task 9 (E2E test) → Task 10 (cleanup)
```

Tasks 1-6 are sequential (each builds on the previous). Tasks 7-8 modify the script independently. Task 9 validates everything end-to-end. Task 10 is cleanup.

## Key Reuse Points

Every function below is imported from the existing codebase — zero reimplementation:

| Function | Source | Used In |
|----------|--------|---------|
| `extract_and_score()` | `ingestion/pdf.py` | Task 2 |
| `validate_parquet_data()` | `ingestion/metadata.py` | Task 4 |
| `validate_with_regex()` | `ingestion/metadata.py` | Task 4 |
| `validate_cross_fields()` | `ingestion/metadata.py` | Task 4 |
| `cross_validate_propositions()` | `ingestion/metadata.py` | Task 4 |
| `merge_metadata()` | `ingestion/metadata.py` | Task 4 |
| `compute_extraction_confidence()` | `ingestion/metadata.py` | Task 4 |
| `extract_acts_cited()` | `legal/extractor.py` | Task 4 |
| `normalize_acts_cited_list()` | `legal/extractor.py` | Task 4 |
| `enrich_statute_cross_references()` | `legal/statute_enrichment.py` | Task 4 |
| `detect_judgment_sections()` | `ingestion/chunker.py` | Task 5 |
| `chunk_judgment()` | `ingestion/chunker.py` | Task 5 |
| `batch_contextualize_chunks()` | `ingestion/contextual_embeddings.py` | Task 5 |
| `_embed_chunks()` | `ingestion/pipeline.py` | Task 5 |
| `_upsert_vectors()` | `ingestion/pipeline.py` | Task 5 |
| `_upsert_proposition_vectors()` | `ingestion/pipeline.py` | Task 5 |
| `_insert_case()` | `ingestion/pipeline.py` | Task 5 |
| `_persist_sections()` | `ingestion/pipeline.py` | Task 5 |
| `_persist_statute_interpretations()` | `ingestion/pipeline.py` | Task 5 |
| `generate_section_summaries()` | `ingestion/section_summarizer.py` | Task 5 |
| `build_pinecone_summary_vectors()` | `ingestion/section_summarizer.py` | Task 5 |
| `_build_citation_graph()` | `ingestion/pipeline.py` | Task 5 |
| `_disable_fts_trigger()` | `scripts/ingest_s3.py` | Task 7 |
| `_enable_fts_trigger()` | `scripts/ingest_s3.py` | Task 7 |
| `_rebuild_fts_vectors()` | `scripts/ingest_s3.py` | Task 7 |
