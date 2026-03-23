# Batch Ingestion Orchestrator — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** New `batch_ingest.py` script using Gemini Batch API (50% cheaper, higher throughput) to ingest 43K SC judgments without modifying any existing pipeline files.

**Architecture:** Mock LLM provider (`BatchCachedLLM`) returns pre-fetched batch results. 3-phase CLI: `submit` (extract text + upload PDFs + submit batch jobs), `poll` (collect results), `process` (feed into existing `ingest_judgment()` unchanged).

**Tech Stack:** `google-genai` SDK (batches + files API), SQLite (batch_state.db), existing pipeline imports.

---

### Task 1: BatchCachedLLM — Mock LLM Provider

**Files:**
- Create: `backend/scripts/batch_llm.py`
- Test: `backend/tests/unit/test_batch_llm.py`

**Step 1: Write the failing test**

```python
"""Tests for BatchCachedLLM mock provider."""

import pytest
from collections.abc import AsyncIterator
from scripts.batch_llm import BatchCachedLLM


class TestBatchCachedLLM:
    """Verify the mock LLM returns cached results correctly."""

    @pytest.fixture
    def sample_result(self) -> dict:
        return {
            "title": "State of Maharashtra v. Doe",
            "citation": "(2023) 5 SCC 123",
            "court": "Supreme Court of India",
            "judge": ["A.K. Sharma", "B.R. Patel"],
            "year": 2023,
            "ratio_decidendi": "The court held...",
            "acts_cited": ["Indian Penal Code, 1860"],
        }

    @pytest.fixture
    def llm(self, sample_result: dict) -> BatchCachedLLM:
        return BatchCachedLLM(result=sample_result)

    @pytest.mark.asyncio
    async def test_generate_structured_from_pdf_returns_cached(self, llm, sample_result):
        result = await llm.generate_structured_from_pdf(
            "/fake/path.pdf",
            prompt="Extract metadata",
            system="You are an expert",
            output_schema={"type": "object"},
        )
        assert result == sample_result

    @pytest.mark.asyncio
    async def test_generate_structured_returns_cached(self, llm, sample_result):
        result = await llm.generate_structured(
            "Extract metadata from this text...",
            system="You are an expert",
            output_schema={"type": "object"},
        )
        assert result == sample_result

    @pytest.mark.asyncio
    async def test_generate_raises_not_implemented(self, llm):
        with pytest.raises(NotImplementedError):
            await llm.generate(prompt="hello")

    @pytest.mark.asyncio
    async def test_stream_raises_not_implemented(self, llm):
        with pytest.raises(NotImplementedError):
            async for _ in llm.stream(prompt="hello"):
                pass

    def test_has_generate_structured_from_pdf_attribute(self, llm):
        """Pipeline checks hasattr(llm, 'generate_structured_from_pdf') to decide PDF path."""
        assert hasattr(llm, "generate_structured_from_pdf")
        assert callable(llm.generate_structured_from_pdf)

    @pytest.mark.asyncio
    async def test_empty_result_passes_through(self):
        """Empty dict from batch should pass through — pipeline handles validation."""
        llm = BatchCachedLLM(result={})
        result = await llm.generate_structured_from_pdf(
            "/fake.pdf", prompt="x", system="y", output_schema={},
        )
        assert result == {}
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_batch_llm.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.batch_llm'`

**Step 3: Write minimal implementation**

```python
"""Mock LLM provider that returns pre-fetched Gemini Batch API results.

Used by batch_ingest.py Phase 3 to feed cached metadata extraction results
into the existing ingest_judgment() pipeline without modifications.

The pipeline calls extract_metadata_llm() which calls:
  1. llm.generate_structured_from_pdf() (if hasattr) — our mock returns the cached result
  2. llm.generate_structured() (fallback) — also returns cached result

The cached result dict is the raw JSON from the Gemini Batch API response,
which should match the structure of interactive generate_structured() output.
"""

from __future__ import annotations

from collections.abc import AsyncIterator


class BatchCachedLLM:
    """LLM provider that returns pre-fetched batch results.

    Implements the LLMProvider protocol just enough for extract_metadata_llm():
    - generate_structured_from_pdf() → cached result (pipeline tries first)
    - generate_structured() → cached result (text fallback)
    - generate() / stream() → NotImplementedError (not needed)
    """

    def __init__(self, result: dict) -> None:
        self._result = result

    async def generate_structured_from_pdf(
        self,
        pdf_path: str,
        *,
        prompt: str,
        system: str | None = None,
        output_schema: dict,
        temperature: float = 0.1,
    ) -> dict:
        return self._result

    async def generate_structured(
        self,
        prompt: str,
        *,
        system: str | None = None,
        output_schema: dict,
        temperature: float = 0.1,
    ) -> dict:
        return self._result

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 8192,
    ) -> str:
        raise NotImplementedError("BatchCachedLLM only supports structured generation")

    async def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        raise NotImplementedError("BatchCachedLLM does not support streaming")
        yield  # pragma: no cover  — makes this a generator
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_batch_llm.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add scripts/batch_llm.py tests/unit/test_batch_llm.py
git commit -m "feat(batch): add BatchCachedLLM mock provider for batch ingestion"
```

---

### Task 2: Batch State SQLite DB

**Files:**
- Create: `backend/scripts/batch_state.py`
- Test: `backend/tests/unit/test_batch_state.py`

**Step 1: Write the failing test**

```python
"""Tests for BatchStateDB — SQLite state tracking for batch ingestion."""

import json
import pytest
from pathlib import Path

from scripts.batch_state import BatchStateDB


class TestBatchStateDB:
    @pytest.fixture
    def db(self, tmp_path: Path) -> BatchStateDB:
        return BatchStateDB(tmp_path / "test_batch_state.db")

    def test_insert_doc(self, db: BatchStateDB):
        db.insert_doc(
            doc_key="year=2023/test.pdf",
            year=2023,
            file_uri="files/abc123",
            text_hash="sha256hex",
            full_text_len=50000,
            parquet_meta={"title": "Test Case"},
            pdf_path="/data/test.pdf",
            api_key_index=0,
        )
        doc = db.get_doc("year=2023/test.pdf")
        assert doc is not None
        assert doc["file_uri"] == "files/abc123"
        assert doc["status"] == "uploaded"

    def test_insert_doc_idempotent(self, db: BatchStateDB):
        """Second insert with same key is ignored."""
        db.insert_doc("k", 2023, "f1", "h", 100, {}, "/p", 0)
        db.insert_doc("k", 2023, "f2", "h", 100, {}, "/p", 0)
        doc = db.get_doc("k")
        assert doc["file_uri"] == "f1"  # first insert wins

    def test_update_status(self, db: BatchStateDB):
        db.insert_doc("k", 2023, "f", "h", 100, {}, "/p", 0)
        db.update_doc_status("k", "submitted", batch_job_name="batches/xyz")
        doc = db.get_doc("k")
        assert doc["status"] == "submitted"
        assert doc["batch_job_name"] == "batches/xyz"

    def test_store_result(self, db: BatchStateDB):
        db.insert_doc("k", 2023, "f", "h", 100, {}, "/p", 0)
        result = {"title": "Extracted Title"}
        db.store_result("k", result)
        doc = db.get_doc("k")
        assert doc["status"] == "completed"
        assert json.loads(doc["llm_result"]) == result

    def test_mark_error(self, db: BatchStateDB):
        db.insert_doc("k", 2023, "f", "h", 100, {}, "/p", 0)
        db.mark_error("k", "batch failed: quota exceeded")
        doc = db.get_doc("k")
        assert doc["status"] == "error"
        assert "quota" in doc["error"]

    def test_get_docs_by_status(self, db: BatchStateDB):
        db.insert_doc("a", 2023, "f1", "h1", 100, {}, "/a", 0)
        db.insert_doc("b", 2023, "f2", "h2", 200, {}, "/b", 0)
        db.store_result("a", {"title": "A"})
        completed = db.get_docs_by_status("completed")
        assert len(completed) == 1
        assert completed[0]["doc_key"] == "a"

    def test_insert_job(self, db: BatchStateDB):
        db.insert_job("batches/j1", api_key_index=0, doc_count=100)
        job = db.get_job("batches/j1")
        assert job["status"] == "pending"
        assert job["doc_count"] == 100

    def test_update_job_status(self, db: BatchStateDB):
        db.insert_job("batches/j1", 0, 50)
        db.update_job_status("batches/j1", "succeeded")
        job = db.get_job("batches/j1")
        assert job["status"] == "succeeded"
        assert job["completed_at"] is not None

    def test_get_pending_jobs(self, db: BatchStateDB):
        db.insert_job("batches/j1", 0, 50)
        db.insert_job("batches/j2", 1, 60)
        db.update_job_status("batches/j1", "succeeded")
        pending = db.get_pending_jobs()
        assert len(pending) == 1
        assert pending[0]["job_name"] == "batches/j2"

    def test_get_docs_for_year(self, db: BatchStateDB):
        db.insert_doc("year=2022/a.pdf", 2022, "f1", "h1", 100, {}, "/a", 0)
        db.insert_doc("year=2023/b.pdf", 2023, "f2", "h2", 200, {}, "/b", 0)
        docs_2023 = db.get_docs_by_status("uploaded", year=2023)
        assert len(docs_2023) == 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_batch_state.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
"""SQLite state tracking for batch ingestion phases.

Tracks individual documents through: uploaded → submitted → completed → processed
Tracks batch jobs through: pending → succeeded → failed
Separate DB from ingest_tracker.db to avoid any interference with the main pipeline.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path


class BatchStateDB:
    """SQLite-backed state for batch ingestion orchestration."""

    def __init__(self, db_path: Path | str = Path("data/batch_state.db")) -> None:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS batch_docs (
                doc_key TEXT PRIMARY KEY,
                year INTEGER,
                file_uri TEXT,
                text_hash TEXT,
                full_text_len INTEGER,
                parquet_meta TEXT,
                pdf_path TEXT,
                api_key_index INTEGER,
                batch_job_name TEXT,
                status TEXT DEFAULT 'uploaded',
                llm_result TEXT,
                error TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS batch_jobs (
                job_name TEXT PRIMARY KEY,
                api_key_index INTEGER,
                status TEXT DEFAULT 'pending',
                doc_count INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            );
        """)
        self._conn.commit()

    # --- Document operations ---

    def insert_doc(
        self,
        doc_key: str,
        year: int,
        file_uri: str,
        text_hash: str,
        full_text_len: int,
        parquet_meta: dict,
        pdf_path: str,
        api_key_index: int,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO batch_docs "
                "(doc_key, year, file_uri, text_hash, full_text_len, parquet_meta, pdf_path, api_key_index) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (doc_key, year, file_uri, text_hash, full_text_len,
                 json.dumps(parquet_meta), pdf_path, api_key_index),
            )
            self._conn.commit()

    def get_doc(self, doc_key: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM batch_docs WHERE doc_key = ?", (doc_key,)
            ).fetchone()
            return dict(row) if row else None

    def update_doc_status(
        self, doc_key: str, status: str, *, batch_job_name: str | None = None
    ) -> None:
        with self._lock:
            if batch_job_name:
                self._conn.execute(
                    "UPDATE batch_docs SET status = ?, batch_job_name = ? WHERE doc_key = ?",
                    (status, batch_job_name, doc_key),
                )
            else:
                self._conn.execute(
                    "UPDATE batch_docs SET status = ? WHERE doc_key = ?",
                    (status, doc_key),
                )
            self._conn.commit()

    def store_result(self, doc_key: str, result: dict) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE batch_docs SET llm_result = ?, status = 'completed' WHERE doc_key = ?",
                (json.dumps(result), doc_key),
            )
            self._conn.commit()

    def mark_error(self, doc_key: str, error: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE batch_docs SET status = 'error', error = ? WHERE doc_key = ?",
                (error, doc_key),
            )
            self._conn.commit()

    def get_docs_by_status(self, status: str, *, year: int | None = None) -> list[dict]:
        with self._lock:
            if year is not None:
                rows = self._conn.execute(
                    "SELECT * FROM batch_docs WHERE status = ? AND year = ?",
                    (status, year),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM batch_docs WHERE status = ?", (status,)
                ).fetchall()
            return [dict(r) for r in rows]

    # --- Job operations ---

    def insert_job(self, job_name: str, api_key_index: int, doc_count: int) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO batch_jobs (job_name, api_key_index, doc_count) VALUES (?, ?, ?)",
                (job_name, api_key_index, doc_count),
            )
            self._conn.commit()

    def get_job(self, job_name: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM batch_jobs WHERE job_name = ?", (job_name,)
            ).fetchone()
            return dict(row) if row else None

    def update_job_status(self, job_name: str, status: str) -> None:
        with self._lock:
            completed = "datetime('now')" if status in ("succeeded", "failed") else "NULL"
            self._conn.execute(
                f"UPDATE batch_jobs SET status = ?, completed_at = {completed} WHERE job_name = ?",
                (status, job_name),
            )
            self._conn.commit()

    def get_pending_jobs(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM batch_jobs WHERE status = 'pending'"
            ).fetchall()
            return [dict(r) for r in rows]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_batch_state.py -v`
Expected: All 11 tests PASS

**Step 5: Commit**

```bash
git add scripts/batch_state.py tests/unit/test_batch_state.py
git commit -m "feat(batch): add BatchStateDB for tracking batch ingestion progress"
```

---

### Task 3: Phase 1 — Submit Command (Core Logic)

**Files:**
- Create: `backend/scripts/batch_ingest.py`
- Reference: `backend/scripts/ingest_s3.py` (import `extract_tar`, `load_parquet_metadata`, `_match_pdf_to_metadata`, `_build_key_pool`, `_strip_language_suffix`)
- Reference: `backend/app/core/ingestion/pdf.py` (import `extract_and_score`)
- Reference: `backend/app/core/ingestion/pipeline.py` (import `_compute_text_hash`)
- Reference: `backend/app/core/legal/prompts.py` (import `METADATA_EXTRACTION_SYSTEM`, `METADATA_EXTRACTION_USER`, `METADATA_OUTPUT_SCHEMA`)

**Step 1: Write the submit command skeleton**

Create `backend/scripts/batch_ingest.py` with:

```python
"""Batch ingestion orchestrator using Gemini Batch API.

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
import hashlib
import json
import logging
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

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
        client.files.upload, file=str(pdf_path),
    )
    return uploaded.name  # e.g. "files/abc123"


def _build_batch_request_entry(doc_key: str, file_uri: str) -> dict:
    """Build one entry for the batch JSONL file."""
    prompt = METADATA_EXTRACTION_USER.format(
        judgment_text="[See attached PDF document]"
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
                "responseSchema": METADATA_OUTPUT_SCHEMA,
                "temperature": 0.1,
            },
        },
    }


async def _load_existing_text_hashes() -> set[str]:
    """Batch-fetch all existing text hashes from PG into a set for O(1) dedup."""
    from sqlalchemy import text
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(
            text("SELECT text_hash FROM cases WHERE text_hash IS NOT NULL")
        )
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
    tar_path, parquet_path = download_year_data(year, data_dir)
    if tar_path is None:
        logger.error("Failed to download tar for year %d, skipping", year)
        return
    extract_dir = data_dir / f"year={year}" / "extracted"

    # Extract PDFs
    pdf_paths = extract_tar(tar_path, extract_dir)
    logger.info("Year %d: %d PDFs extracted", year, len(pdf_paths))

    # Load parquet metadata
    metadata_map = load_parquet_metadata(parquet_path)
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
    logger.info("Year %d: %d new PDFs to process (skipping %d already tracked)", year, len(new_pdfs), len(pdf_paths) - len(new_pdfs))

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
            year, wave_start // wave_size + 1, len(wave), current_key_idx,
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
                        logger.warning("Skipping %s: too short (%d chars)", doc_key, text_quality.char_count)
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
                client.files.upload, file=jsonl_path,
            )

            # Submit batch job
            batch_job = await asyncio.to_thread(
                client.batches.create,
                model="models/gemini-2.5-flash",
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
                    entry["key"], "submitted", batch_job_name=job_name,
                )

            logger.info(
                "Submitted batch job %s: %d requests (key %d)",
                job_name, len(sub_batch), current_key_idx,
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
                client.files.download, name=result_file_name,
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
            for entry in (job.dest.inlined_responses or []):
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
    from app.core.database import async_session_factory
    from app.core.ingestion.pipeline import ingest_judgment
    from app.core.providers.embeddings.gemini import GeminiEmbedder
    from app.core.providers.vector.pinecone_store import PineconeStore
    from app.core.providers.graph.neo4j_store import Neo4jStore
    from app.core.providers.storage.local_store import LocalFileStorage
    from scripts.batch_llm import BatchCachedLLM
    from scripts.ingest_s3 import IngestTracker, RateLimiterPool

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
                    embed_limiter_pool.get(api_keys[embed_idx])
                    if embed_limiter_pool else None
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
                    eta_str = f"{int(eta_min // 60)}h {int(eta_min % 60)}m" if eta_min >= 60 else f"{int(eta_min)}m"
                    logger.info(
                        "Phase 3: %d/%d (%.1f%%) | %.1f/min | ETA: %s | %d failed",
                        stats["success"], len(all_docs),
                        total / len(all_docs) * 100,
                        rate, eta_str, stats["failed"],
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
        stats["success"], stats["failed"], len(all_docs),
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
            asyncio.run(submit_year(
                year, api_keys, state_db,
                Path(args.data_dir),
                wave_size=args.wave_size,
                concurrency=args.concurrency,
            ))

    elif args.command == "poll":
        asyncio.run(poll_jobs(api_keys, state_db, interval=args.interval))

    elif args.command == "process":
        asyncio.run(process_completed(
            api_keys, state_db,
            year_from=args.year_from,
            year_to=args.year_to,
            concurrency=args.concurrency,
            rpm_limit=args.rpm_limit,
        ))


if __name__ == "__main__":
    main()
```

**Step 2: Verify imports resolve**

Run: `cd backend && python -c "from scripts.batch_ingest import main; print('OK')"`
Expected: `OK` (may need to adjust imports based on what's actually exported from ingest_s3.py)

**Step 3: Commit**

```bash
git add scripts/batch_ingest.py
git commit -m "feat(batch): add batch_ingest.py orchestrator — submit/poll/process CLI"
```

---

### Task 4: E2E Smoke Test — Single Case Through All 3 Phases

This is the critical validation step. Test one real case end-to-end.

**Step 1: Submit one case**

```bash
cd backend
GEMINI_API_KEYS="your_key" python -m scripts.batch_ingest submit --year-from 2023 --year-to 2023 --wave-size 1
```

Verify:
- `data/batch_state.db` has 1 row in `batch_docs` with `status='submitted'`
- `batch_jobs` has 1 row with `status='pending'`
- Gemini Files API upload succeeded (check logs for file_uri)

**Step 2: Poll for results**

```bash
GEMINI_API_KEYS="your_key" python -m scripts.batch_ingest poll --interval 30
```

Wait for job to complete. Verify:
- `batch_docs.status = 'completed'`
- `batch_docs.llm_result` is valid JSON with title/citation

**Step 3: Compare batch result vs interactive result**

```python
# Compare batch LLM result with what interactive extraction produces
import json
from scripts.batch_state import BatchStateDB

db = BatchStateDB()
doc = db.get_docs_by_status("completed")[0]
batch_result = json.loads(doc["llm_result"])

# Run interactive extraction on the same PDF for comparison
# (use the existing ingest_s3 pipeline on the same PDF)
# Check: do both produce similar title, citation, court, acts_cited?
print(json.dumps(batch_result, indent=2))
```

**Step 4: Process the case**

```bash
GEMINI_API_KEYS="your_key" python -m scripts.batch_ingest process --year-from 2023 --year-to 2023
```

Verify:
- Case appears in PostgreSQL `cases` table
- Chunks in Pinecone (query by case_id)
- Citation graph in Neo4j
- `batch_docs.status = 'processed'`

**Step 5: Commit and tag**

```bash
git add -A
git commit -m "feat(batch): e2e smoke test passed — batch ingestion pipeline verified"
```

---

### Task 5: Iteration — Fix Batch Response Format (if needed)

After the smoke test, the most likely issue is the batch response JSON structure differing from interactive. The interactive `generate_structured_from_pdf()` returns a raw `dict` (the parsed JSON). The batch API wraps results in:

```json
{"key": "doc_key", "response": {"candidates": [{"content": {"parts": [{"text": "{...json...}"}]}}]}}
```

The `_process_result_entry()` function in Phase 2 already handles this unwrapping. But if the structure differs, adjust `_process_result_entry()` accordingly. The `BatchCachedLLM` receives the already-unwrapped dict, so no changes needed there.

**If the Gemini SDK provides a helper for parsing batch results**, use it instead of manual JSON navigation. Check: `job.dest.inlined_responses` may already return parsed results.

---

### Task 6: Production Run — Full 43K

After smoke test passes, run the full ingestion:

```bash
# Phase 1: Submit all years in waves
for YEAR in $(seq 2015 2023); do
  GEMINI_API_KEYS="key1,key2,key3,key4,key5" \
  python -m scripts.batch_ingest submit --year-from $YEAR --year-to $YEAR --wave-size 5000 --concurrency 10
done

# Phase 2: Poll until all complete
GEMINI_API_KEYS="key1,key2,key3,key4,key5" \
python -m scripts.batch_ingest poll --interval 60

# Phase 3: Process all results
GEMINI_API_KEYS="key1,key2,key3,key4,key5" \
python -m scripts.batch_ingest process --year-from 2015 --year-to 2023 --concurrency 20

# Post-processing: FTS rebuild
DATABASE_URL="..." python -m scripts.ingest_s3 rebuild-fts
```

Monitor: `sqlite3 data/batch_state.db "SELECT status, COUNT(*) FROM batch_docs GROUP BY status"`
