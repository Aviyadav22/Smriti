# Pipeline Audit V2 — Implementation Checklist

**Plan file**: `docs/plans/2026-03-21-pipeline-audit-v2-fixes.md`
**Status**: IN PROGRESS
**Test command**: `cd backend && python -m pytest tests/unit/ -x -q`
**Total steps**: 22 (7 phases)

---

## Phase 1: Migration Chain Fixes

- [x] **1.1** Fix migration 028 — change `op.add_column` to `op.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS coram_size INTEGER")` and make downgrade a no-op (migration 011 owns this column)
  - File: `backend/migrations/versions/028_coram_size.py`
  - Verify: Read migration 011 to confirm it adds coram_size first
  - E2E: No runtime code changes. Fresh `alembic upgrade head` must pass.

---

## Phase 2: FTS Trigger Overhaul

- [x] **2.1** Create migration 030 — replace FTS trigger function (remove `updated_at := NOW()`) and recreate trigger with `UPDATE OF` clause limiting to FTS-relevant columns
  - File: NEW `backend/migrations/versions/030_fts_trigger_optimization.py`
  - revision="030", down_revision="029"
  - MUST include: DROP TRIGGER + CREATE TRIGGER with UPDATE OF clause
  - MUST include: CREATE OR REPLACE FUNCTION without `NEW.updated_at := NOW()`
  - Verify: Read migration 025 for current trigger function to know exactly what to replace
  - E2E: After this, updates to `ingestion_status`, `chunk_count`, `enrichment_status`, `cited_by_count` etc. will NOT trigger FTS recompute

- [x] **2.2** Add explicit `updated_at = NOW()` to ALL raw SQL in pipeline.py that updates the `cases` table
  - File: `backend/app/core/ingestion/pipeline.py`
  - Locations to find and update:
    - The main INSERT in `_insert_case()` — add `updated_at` column + `NOW()` value
    - The UPDATE at ~line 435 (`SET chunk_count=..., ingestion_status=...`) — add `, updated_at = NOW()`
    - The UPDATE in status-change blocks (`ingestion_status = 'failed'`) — add `, updated_at = NOW()`
    - The UPDATE in `_record_ingestion_failure()` — add `, updated_at = NOW()`
  - Verify: grep for `UPDATE cases SET` and `INSERT INTO cases` in pipeline.py to find ALL locations
  - E2E: `_reconcile_orphans()` in ingest_s3.py depends on `updated_at` being fresh — must still work

- [x] **2.3** Run tests after Phase 2 — `python -m pytest tests/unit/ -x -q`
  - Fix any failures (likely in test_ingestion_pipeline.py if SQL string assertions changed)

---

## Phase 3: Ingestion Script Hardening

- [x] **3.1** Remove 660s gather timeout — replace `asyncio.wait_for(asyncio.gather(*workers), timeout=660.0)` with plain `asyncio.gather(*workers, return_exceptions=True)`
  - File: `backend/scripts/ingest_s3.py` (find `asyncio.wait_for` wrapping `asyncio.gather`)
  - Also remove the associated `except asyncio.TimeoutError` block that handles gather timeout
  - E2E: Per-document 600s timeout (line ~739) remains as the real safety net. Years with many docs will now complete fully.

- [x] **3.2** Move shutdown_event inside main() — remove module-level `shutdown_event` and `_event_loop`, create inside `main()`, pass to `ingest_year()`
  - File: `backend/scripts/ingest_s3.py`
  - Changes needed:
    - Remove module-level `shutdown_event = asyncio.Event()` and `_event_loop = None`
    - Create both inside `async def main()` using `asyncio.get_running_loop()`
    - Add `shutdown_event` parameter to `ingest_year()` signature
    - Update signal handler setup to use the local references
    - Update all `shutdown_event.is_set()` calls in `_worker()` and year loop
  - E2E: Functionally identical. Cleaner lifecycle. Signal handling now testable.

- [x] **3.3** Atomic tar downloads — download to `.tmp` suffix, rename on completion
  - File: `backend/scripts/ingest_s3.py` — `_download_with_timeout()` function
  - Fix: `tmp_dest = dest.with_suffix(dest.suffix + ".tmp")`, write to tmp_dest, then `tmp_dest.rename(dest)`
  - E2E: Interrupted downloads are no longer treated as valid on resume. The `.tmp` file gets overwritten on retry.

- [x] **3.4** Guard SIGTERM on Windows — wrap in `sys.platform != "win32"` check
  - File: `backend/scripts/ingest_s3.py` — signal handler registration
  - Fix: `if sys.platform != "win32": signal.signal(signal.SIGTERM, _handle_shutdown)`
  - E2E: No behavior change on Linux/macOS. Prevents silent failure on Windows.

- [x] **3.5** Run tests after Phase 3 — `python -m pytest tests/unit/ -x -q`

---

## Phase 4: Provider Reliability

- [x] **4.1** Add tenacity retry to GCS storage
  - File: `backend/app/core/providers/storage/gcs_storage.py`
  - Add `from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type`
  - Define `_gcs_retry` decorator: 3 attempts, exponential 1-15s, retry on `(OSError, ConnectionError, TimeoutError, Exception)` — but be specific, don't catch ValueError etc.
  - Apply to: `store()`, `retrieve()`, `retrieve_chunked()`, `delete()`, `exists()`
  - E2E: GCS transient failures now auto-retry. Pipeline `except` blocks still catch after all retries exhaust.
  - Test impact: Check `test_gcs_storage.py` — if tests mock failures and assert `call_count == 1`, they will break (now retries 3x). Update those tests.

- [x] **4.2** Add Neo4j explicit transactions for batch ops
  - File: `backend/app/core/providers/graph/neo4j_store.py`
  - Modify `batch_create_nodes()` and `batch_create_citation_edges()`
  - Change from `session.run(query, ...)` to `async with session.begin_transaction() as tx: await tx.run(query, ...); await tx.commit()`
  - E2E: Each batch is atomic. Failed batch = only that batch rolls back. Previously committed batches are safe (MERGE is idempotent anyway).
  - Test impact: None — tests mock at higher level

- [x] **4.3** Strengthen Neo4j retry — change from 3 attempts/10s max to 5 attempts/30s max
  - File: `backend/app/core/providers/graph/neo4j_store.py` — `_neo4j_retry` decorator definition
  - Change: `stop_after_attempt(3)` → `5`, `max=10` → `30`, `min=1` → `2`
  - E2E: Longer backoff = higher success rate under AuraDB load. Total max wait ~62s (was ~11s).
  - Test impact: None

- [x] **4.4** Run tests after Phase 4 — `python -m pytest tests/unit/ -x -q`

---

## Phase 5: Data Quality Fixes

- [x] **5.1** Fix party_counsel field name mismatch — change pipeline.py to use `"name"` instead of `"counsel_name"`
  - File: `backend/app/core/ingestion/pipeline.py` — find `_build_citation_graph` or counsel node creation section
  - Search for: `counsel_name` in pipeline.py
  - Replace with: `name` (matching the LLM schema and validate_with_regex in metadata.py)
  - Verify: Read `backend/app/core/legal/prompts.py` to confirm the LLM schema uses `"name"` for counsel
  - E2E: Counsel nodes in Neo4j will now have proper names. Previously all were empty strings.
  - Test impact: `test_35k_hardening.py::test_party_counsel_invalid_filtered` uses `"name"` — no change needed

- [x] **5.2a** Add `warnings` column to IngestTracker for post-run analysis
  - File: `backend/scripts/ingest_s3.py` — `IngestTracker._migrate_schema()`
  - Add column: `warnings TEXT` to `ingestion_progress` table (with ALTER TABLE migration for existing DBs)
  - Add method: `add_warning(doc_key, warning)` that appends to comma-separated warnings string
  - E2E: After full 35K run, query `SELECT doc_key, warnings FROM ingestion_progress WHERE warnings IS NOT NULL` to find cases needing special re-processing

- [x] **5.2b** Add MAX_OCR_PAGES guard (500 pages) for full-document OCR + truncation tracking
  - File: `backend/app/core/ingestion/pdf.py`
  - Add: `MAX_OCR_PAGES = 500` constant near `MAX_PAGES = 5000`
  - Apply ONLY in `extract_with_ocr()` / `_ocr_sync()` — the full-document OCR path. Replace the `MAX_PAGES` check there with `MAX_OCR_PAGES`. Process first MAX_OCR_PAGES pages instead of returning empty string.
  - Do NOT limit per-page OCR fallback in `_extract_pdf_text_sync()` — that only OCRs individual bad pages, not the whole doc
  - When truncated: log `logger.warning(...)` and return the partial text (NOT empty)
  - Add `ocr_truncated: bool = False` and `ocr_total_pages: int = 0` fields to `TextQuality` dataclass
  - Set these in `extract_and_score()` when OCR truncation occurs
  - E2E: Truncated cases still get ingested with partial text (better than nothing). Cases are flagged for post-run re-processing.

- [x] **5.2c** Wire truncation warnings from pipeline to IngestTracker
  - File: `backend/app/core/ingestion/pipeline.py` — return truncation info from `ingest_judgment()`
  - File: `backend/scripts/ingest_s3.py` — in `_process_one()`, after successful ingestion, check for truncation warnings and record via `tracker.add_warning(doc_key, f"ocr_truncated:{pages_ocrd}/{total_pages}")`
  - E2E: After full run, query tracker for truncated cases → re-ingest individually with higher limits or manual OCR
  - Test impact: None — tracker changes are additive

- [x] **5.3** Add line-length heuristic to section detection
  - File: `backend/app/core/ingestion/chunker.py` — `_is_heading_position()` function
  - Fix: After determining `line_start` and before checking `prefix`, compute `line_end` and `line_length`. If `line_length > 100`, return `False` (body text, not a heading).
  - E2E: Fewer false section breaks. Chunks may be larger. Only affects future ingestions, not existing vectors.
  - Test impact: Write a new test verifying "15. Evidence shows that the accused..." is NOT detected as EVIDENCE heading

- [x] **5.4** Run tests after Phase 5 — `python -m pytest tests/unit/ -x -q`

---

## Phase 6: Schema Hardening

- [x] **6.1** Create migration 031 — unique partial index on text_hash
  - File: NEW `backend/migrations/versions/031_text_hash_unique_index.py`
  - revision="031", down_revision="030"
  - SQL: `CREATE UNIQUE INDEX IF NOT EXISTS ix_cases_text_hash_unique ON cases (text_hash) WHERE text_hash IS NOT NULL`
  - NOTE: Do NOT use CONCURRENTLY inside an Alembic migration transaction (it's incompatible). Use regular CREATE INDEX.
  - Before creating: Check for existing duplicate text_hash values. If any exist, the index creation will fail. Add a pre-step to dedup.
  - Pre-step SQL: `DELETE FROM cases a USING cases b WHERE a.id > b.id AND a.text_hash = b.text_hash AND a.text_hash IS NOT NULL`
  - E2E: After this, concurrent duplicate inserts raise UniqueViolation instead of creating duplicates.

- [x] **6.2** Handle text_hash UniqueViolation in pipeline INSERT
  - File: `backend/app/core/ingestion/pipeline.py` — `_insert_case()` function
  - After the INSERT, catch `asyncpg.exceptions.UniqueViolationError` (or `IntegrityError` via SQLAlchemy) for the text_hash constraint specifically.
  - On catch: SELECT the existing case by text_hash, return `(existing_id, True)` as if it was already ingested.
  - E2E: Concurrent ingestion of the same document now safely deduplicates instead of crashing.
  - Test impact: May need to update `test_concurrent_ingestion.py`

- [x] **6.3** Run tests after Phase 6 — `python -m pytest tests/unit/ -x -q`

---

## Phase 7: Model Sync & Final Verification

- [x] **7.1** Sync model `__table_args__` with all migration-created indexes and constraints
  - File: `backend/app/models/case.py` — `__table_args__` tuple
  - Add all missing indexes from migrations 011, 019, 023, 029, 030, 031
  - Add all missing CHECK constraints from migrations 011, 022, 029
  - Use `Index("name", "column", ...)` for regular indexes
  - Use `CheckConstraint("expr", name="name")` for CHECK constraints
  - Read each migration to get exact index/constraint definitions
  - E2E: Prevents `alembic --autogenerate` from dropping these indexes

- [x] **7.2** Run full test suite — `python -m pytest tests/ -x -q`
  - All tests must pass
  - If any fail, fix them before proceeding

- [x] **7.3** Apply migrations to database — migrations 032 + 033 applied cleanly, head = 033

---

## Completion Criteria

All boxes above must be checked. Final state:
- [x] All 22 steps completed
- [x] All tests passing (2029 unit + 59 integration, excluding live-DB search accuracy + quality tests)
- [x] Database at migration 033 (head)
- [x] No CRITICAL or HIGH issues remain
