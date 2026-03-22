# Ingestion 35K Hardening — Implementation Checklist

> **For Opus Ralph-Loop Agent**: Read this file at the start of each loop iteration.
> Find the first unchecked `[ ]` item, implement it, run verification, then update `[ ]` → `[x]`.
> Always read the **E2E notes** before implementing — they describe cross-step dependencies.
>
> **Plan file**: `docs/plans/2026-03-21-ingestion-35k-hardening.md` (full implementation details)
> **Test command**: `cd backend && python -m pytest tests/unit/ --tb=short -q`
> **Migration command**: `cd backend && DATABASE_URL="postgresql+asyncpg://***REMOVED***:***REMOVED***@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres" PYTHONPATH=. alembic upgrade head`

---

## Phase 1: FTS Trigger Regression Fix (CRITICAL — do first)

- [x] **1.1** Create `backend/migrations/versions/025_fix_fts_trigger_v3.py`
  - Upgrade: `CREATE OR REPLACE FUNCTION cases_searchable_text_update()` with ALL 17 fields:
    - A: title, citation, case_number
    - B: court, judge[], petitioner, respondent, **headnotes**, **outcome_summary**
    - C: description, ratio_decidendi, operative_order
    - D: keywords[], acts_cited[], legal_principles_applied[], issue_classification[], full_text(**500000**)
  - Add `NEW.updated_at := NOW();` before `RETURN NEW;`
  - Add `UPDATE cases SET title = title;` to trigger tsvector rebuild for existing rows
  - Downgrade: restore migration 024's function body exactly
  - `revision = "025"`, `down_revision = "024"`
  - **Verify**: `alembic upgrade head` succeeds; query `SELECT searchable_text IS NOT NULL FROM cases LIMIT 1` returns true
  - **E2E**: This MUST be step 1 — all subsequent ingested cases depend on correct FTS trigger. The tsvector rebuild updates `updated_at` for all existing rows (which also tests the `updated_at := NOW()` fix).

---

## Phase 2: Rate Limiting & Timeouts (CRITICAL — safety nets before performance work)

- [x] **2.1** Add `rate_limiter` param to `batch_contextualize_chunks()`
  - File: `backend/app/core/ingestion/contextual_embeddings.py`
  - Add `rate_limiter: AsyncRateLimiter | None = None` to function signature
  - Call `await rate_limiter.acquire()` before each LLM call inside the task loop
  - File: `backend/app/core/ingestion/pipeline.py` (~line 321)
  - Pass `rate_limiter=llm_rate_limiter` in the call
  - **Verify**: `grep -n "rate_limiter" backend/app/core/ingestion/contextual_embeddings.py` shows the param
  - **E2E**: Depends on nothing. But Step 10.1 tests will verify this. Any test that calls `batch_contextualize_chunks` directly must add `rate_limiter=None`.

- [x] **2.2** Add timeout to `GeminiEmbedder.embed_batch()` and `embed_text()`
  - File: `backend/app/core/providers/embeddings/gemini.py`
  - Wrap API calls in `asyncio.wait_for(..., timeout=120.0)` for batch, `60.0` for single
  - Add `import asyncio` if not present
  - **Verify**: `grep -n "wait_for" backend/app/core/providers/embeddings/gemini.py` shows timeouts
  - **E2E**: Independent of other steps. The `_embedding_retry` decorator will catch `TimeoutError` and retry.

- [x] **2.3** Add per-worker timeout in `ingest_s3.py`
  - File: `backend/scripts/ingest_s3.py` (~line 673)
  - Wrap `ingest_judgment()` in `asyncio.wait_for(..., timeout=600.0)`
  - Catch `asyncio.TimeoutError`, call `tracker.mark_failed(doc_key, "timeout_600s")`, increment `stats["failed"]`
  - **Verify**: `grep -n "wait_for.*600" backend/scripts/ingest_s3.py` shows the timeout
  - **E2E**: Depends on nothing. Enables Step 2.4 (shutdown timeout) to work correctly — workers now guaranteed to finish within 600s.

- [x] **2.4** Add timeout to `asyncio.gather` in shutdown
  - File: `backend/scripts/ingest_s3.py` (~line 770)
  - Wrap gather in `asyncio.wait_for(..., timeout=660.0)`, cancel workers on timeout
  - **Verify**: `grep -n "660" backend/scripts/ingest_s3.py` shows the gather timeout
  - **E2E**: Depends on Step 2.3 (per-worker timeout). Together they guarantee shutdown completes in bounded time.

---

## Phase 3: LLM Reliability (CRITICAL — fix before any large run)

- [x] **3.1** Add text truncation in `extract_metadata_llm()`
  - File: `backend/app/core/ingestion/metadata.py`
  - Add `_truncate_for_llm(text, head=30000, tail=20000)` helper function
  - Apply to text-fallback path: `truncated = _truncate_for_llm(text)` before `format(judgment_text=truncated)`
  - Do NOT truncate for PDF multimodal path (Gemini handles full PDF natively)
  - **Verify**: Add a unit test that verifies truncation of a 100K char string
  - **E2E**: Independent. Only affects the LLM prompt — chunking, FTS, and display still use full `full_text`.

- [x] **3.2** Fix all-null response detection
  - File: `backend/app/core/ingestion/metadata.py` (~line 207)
  - Change `if not result:` → `if not result or all(v is None for v in result.values()):`
  - **Verify**: Add a unit test with `{"title": None, "year": None}` input → raises RuntimeError
  - **E2E**: Independent. The RuntimeError triggers retry (made retryable in previous session).

- [x] **3.3** Remove inner retry loop in `extract_metadata_llm`
  - File: `backend/app/core/ingestion/metadata.py`
  - Remove the `for attempt in range(max_retries):` loop structure
  - Remove the `max_retries` parameter from function signature
  - Remove manual `asyncio.sleep(backoff)` between attempts
  - Keep the try/except for (ValueError, KeyError) as non-retryable
  - Let all other exceptions propagate to the pipeline's tenacity decorator
  - **Verify**: `grep -n "max_retries" backend/app/core/ingestion/metadata.py` shows no results (parameter removed)
  - **E2E**: Requires updating `test_metadata_llm_retry.py` — the test tests the inner retry loop which no longer exists. The pipeline-level retry (`pipeline.py` ~line 169) still provides 3 retries. Also check that no other code passes `max_retries=` to `extract_metadata_llm`.
  - **IMPORTANT**: Search the entire codebase for callers of `extract_metadata_llm` to ensure none pass `max_retries`.

---

## Phase 4: Batching & Performance (HIGH — reduce DB/Graph round-trips)

- [x] **4.1** Bulk INSERT for `_persist_sections`
  - File: `backend/app/core/ingestion/pipeline.py` (~line 1178)
  - Replace for-loop with single `db.execute(text(...), list_of_dicts)` for executemany
  - Keep `ON CONFLICT DO NOTHING`
  - **Verify**: Run test suite — `_persist_sections` called via `ingest_judgment` in integration tests
  - **E2E**: Independent. Same SQL semantics, just batched. Must verify SQLAlchemy text() + list produces executemany with asyncpg.

- [x] **4.2** Bulk INSERT for `_persist_citation_equivalents`
  - File: `backend/app/core/ingestion/pipeline.py` (~line 1201)
  - Same pattern as 4.1
  - **Verify**: Same as 4.1
  - **E2E**: Independent. Same approach as 4.1.

- [x] **4.3** Batch Neo4j V2 enrichment with UNWIND
  - File: `backend/app/core/ingestion/pipeline.py` (~line 1044)
  - Replace 4 for-loops (citation_treatments, party_counsel, legal_principles, issue_classification) with 4 UNWIND queries
  - Test that empty lists produce no errors (UNWIND on empty list = no rows = no-op)
  - **Verify**: `grep -n "UNWIND" backend/app/core/ingestion/pipeline.py` shows 4+ UNWIND patterns
  - **E2E**: Depends on Step 8.1 (Neo4j constraints) for performance, but works correctly without them. Step 7.1 (V2 validation) ensures the data passed to UNWIND is clean. Implement this before 8.1 — it works without constraints, just slower.

---

## Phase 5: Resource Management (HIGH — disk, connections, thread safety)

- [x] **5.1** Clean up PDFs after processing
  - File: `backend/scripts/ingest_s3.py`
  - After successful `ingest_judgment()`: `pdf_path.unlink(missing_ok=True)`
  - After all cases for a year: delete tar + extracted dir with `shutil.rmtree`
  - Add `import shutil` if needed
  - Do NOT delete on failure (PDF needed for retry)
  - **Verify**: Run `ls data/year=2020/extracted/` after a small test — should be empty after success
  - **E2E**: Independent. Must happen AFTER `ingest_judgment()` completes (PDF needed for multimodal extraction). Failed cases keep their PDF for retry — but tar is re-downloadable anyway.

- [x] **5.2** Increase PG pool size
  - File: `backend/app/core/config.py` (~line 34)
  - Change `database_pool_size: int = 5` → `15`
  - **Verify**: `grep "pool_size" backend/app/core/config.py`
  - **E2E**: Independent. Supports 10 concurrent workers + overhead. No effect on tests.

- [x] **5.3** Add threading.Lock to IngestTracker
  - File: `backend/scripts/ingest_s3.py` (~line 109)
  - Add `self._lock = threading.Lock()` in `__init__`
  - Wrap all write methods (`mark_success`, `mark_failed`, `mark_stage`, `init_doc`) with `with self._lock:`
  - Wrap read methods (`is_processed`, `detailed_stats`) too for consistency
  - Add `import threading` if not present
  - **Verify**: `grep -n "_lock" backend/scripts/ingest_s3.py` shows lock usage in all methods
  - **E2E**: Independent. Prevents SQLite corruption under concurrent writes.

---

## Phase 6: Error Handling & Resilience (HIGH)

- [x] **6.1** Fix `_record_ingestion_failure` — use separate session
  - File: `backend/app/core/ingestion/pipeline.py` (~line 828)
  - Change function to not accept `db` parameter — create its own session via `async_session_factory()`
  - Update all callers (~line 510) to not pass `db`
  - Add `from app.db.postgres import async_session_factory` import
  - **Verify**: `grep -n "async_session_factory" backend/app/core/ingestion/pipeline.py` shows the import
  - **E2E**: Depends on Step 5.2 (pool size increase) — the fresh session uses an extra connection briefly. Also check that `audit_log` table exists (should exist from previous migrations).

- [x] **6.2** Add startup API key validation
  - File: `backend/scripts/ingest_s3.py`
  - Add `_validate_api_keys()` async function that probes each key
  - Call before workers start; remove bad keys from pool
  - Abort if ALL keys are invalid
  - **Verify**: Temporarily use a bad key and verify it's detected at startup
  - **E2E**: Independent. Uses a minimal LLM call — check the `LLMProvider` protocol for available methods. Use `generate_structured` with a trivial schema or `generate` with minimal text. Must handle both `GeminiLLM` and any other provider.

- [x] **6.3** Add startup orphan reconciliation
  - File: `backend/scripts/ingest_s3.py`
  - Add `_reconcile_orphans()` that resets `ingestion_status = 'processing'` rows older than 1 hour to `'failed'`
  - Call at start of `run()` command
  - **Verify**: Insert a fake 'processing' row, run reconciliation, verify it's reset to 'failed'
  - **E2E**: Depends on Step 5.2 (pool size) for the DB connection. The tracker will re-process these cases on next run since they won't be in the tracker's `processed` table.

- [x] **6.4** Fix `ingestion_status` default + create migration 026
  - File: `backend/app/models/case.py` (~line 60) — change `server_default="complete"` → `"pending"`
  - File: `backend/migrations/versions/026_schema_hardening.py` — see Step 9.1 (combined migration)
  - **Verify**: Defer to Step 9.1 (this is combined into the schema hardening migration)
  - **E2E**: Must be done together with Step 9.1 to avoid multiple tiny migrations. Mark this step done when 9.1 is done.

---

## Phase 7: Data Quality (MEDIUM)

- [x] **7.1** Add V2 field validation in `validate_with_regex()`
  - File: `backend/app/core/ingestion/metadata.py`
  - Add validation for: `judicial_tone` (enum), `filing_date` (ISO), `hearing_count` (range), `operative_order` (length), all V2 list fields (type check, dedup, cap), `citation_treatments` (dict structure), `party_counsel` (dict structure)
  - **Verify**: Add unit tests for each validation rule
  - **E2E**: Must come BEFORE Step 4.3 in execution order if possible (validates data before Neo4j writes), but technically works in any order since validation runs before graph building in the pipeline. The plan file has detailed validation code.

- [x] **7.2** Extend editorial regex for SCC/AIR/SCALE/MANU reporters
  - File: `backend/app/core/ingestion/pdf.py` (~line 76)
  - Add 4 new patterns to `_REPORTER_PAGE_MARKER_RE`: SCC, AIR, SCALE, MANU
  - **Verify**: Add parametrized test cases to `test_editorial_filters.py`
  - **E2E**: Independent. Affects text cleaning which feeds into FTS and Pinecone. No cross-dependencies.

- [x] **7.3** Add control character stripping
  - File: `backend/app/core/ingestion/pdf.py` — in `clean_extracted_text()` after NFKC normalization
  - Add `text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)`
  - **Verify**: Unit test with NUL byte in input → removed in output
  - **E2E**: Independent. Must come after NFKC normalization (which is already step 1 in `clean_extracted_text`).

---

## Phase 8: Neo4j & Pinecone Optimization (MEDIUM)

- [x] **8.1** Add Neo4j unique constraints for V2 node types
  - File: `backend/app/core/providers/graph/neo4j_store.py` — in `ensure_constraints()` (~line 200)
  - Add constraints for `Counsel.name`, `LegalPrinciple.name`, `Issue.tag`
  - Use `IF NOT EXISTS` for idempotency
  - **Verify**: Run `ensure_constraints()` and check Neo4j browser for new constraints
  - **E2E**: Step 4.3 (UNWIND queries) works without constraints but is slow. Constraints make MERGE operations O(1) instead of O(n). Must run `ensure_constraints()` before 35K ingestion.

- [x] **8.2** Configure Neo4j connection pool explicitly
  - File: `backend/app/core/providers/graph/neo4j_store.py` (~line 70)
  - Add `max_connection_pool_size=30` and `connection_acquisition_timeout=30.0` to driver constructor
  - **Verify**: `grep -n "max_connection_pool_size" backend/app/core/providers/graph/neo4j_store.py`
  - **E2E**: Independent. Prevents connection exhaustion on AuraDB free tier.

---

## Phase 9: Schema Hardening (MEDIUM)

- [x] **9.1** Create migration 026 — combined schema hardening
  - File: `backend/migrations/versions/026_schema_hardening.py`
  - `revision = "026"`, `down_revision = "025"`
  - Include ALL of these in upgrade():
    1. `ALTER TABLE cases ALTER COLUMN ingestion_status SET DEFAULT 'pending'` (from Step 6.4)
    2. `ADD CONSTRAINT ck_cases_enrichment_status CHECK (...)` for flash_only/pro_enriched/failed
    3. `CREATE INDEX IF NOT EXISTS ix_cases_author_judge ON cases (author_judge) WHERE author_judge IS NOT NULL`
    4. `CREATE INDEX IF NOT EXISTS ix_cases_court_decision_date ON cases (court, decision_date DESC)`
  - Downgrade: reverse all (DROP CONSTRAINT, DROP INDEX, restore default)
  - **Verify**: `alembic upgrade head` succeeds
  - **E2E**: Depends on Step 1.1 (migration 025) being in the chain. This is `down_revision = "025"`. Must also update `backend/app/models/case.py` `server_default` (Step 6.4).

---

## Phase 10: Tests & Final Verification

- [x] **10.1** Write new test file `backend/tests/unit/test_35k_hardening.py`
  - Tests for: truncation helper, all-null detection, V2 validation, control char stripping, extended editorial regex, bulk section INSERT mock, UNWIND mock, worker timeout handling, SQLite lock safety
  - Use existing mock patterns from conftest.py (AsyncMock, patch)
  - **E2E**: Must cover all changes from Phases 1-9. Use parametrized tests for regex patterns.

- [x] **10.2** Update existing tests
  - `test_metadata_llm_retry.py`: Remove/update tests for inner retry loop; verify pipeline-level retry still works
  - `test_editorial_filters.py`: Add SCC/AIR/SCALE/MANU parametrized cases
  - Any test calling `batch_contextualize_chunks`: add `rate_limiter=None` kwarg
  - **Verify**: `grep -rn "batch_contextualize_chunks" backend/tests/` to find all callers
  - **E2E**: These test updates are required by Steps 2.1 and 3.3. If tests fail, those steps' code changes may be wrong.

- [x] **10.3** Run full test suite — must be 0 failures
  - Command: `cd backend && python -m pytest tests/unit/ --tb=short -q`
  - If failures: fix the code, not the tests (unless the test itself was wrong)
  - Record the final test count here: `2026 passed, 0 failed`
  - **E2E**: This validates ALL previous steps together.

- [ ] **10.4** Apply migrations and run E2E ingestion test
  - Apply: `alembic upgrade head` (migrations 025 + 026)
  - Run: `python scripts/ingest_s3.py run --year 2020 --limit 3`
  - Verify ALL of these:
    1. `SELECT headnotes, outcome_summary, searchable_text IS NOT NULL FROM cases WHERE year=2020 LIMIT 1` — headnotes populated, FTS vector exists
    2. No hung workers (completes within 10 min)
    3. `ls data/year=2020/extracted/` — PDFs cleaned up
    4. Neo4j: `MATCH (lp:LegalPrinciple) RETURN count(lp)` — principles created via UNWIND
    5. No "database is locked" errors in logs
    6. `SELECT ingestion_status FROM cases ORDER BY created_at DESC LIMIT 1` — should be 'complete' (not 'pending', since pipeline explicitly sets it)
  - Record results here: `E2E: ______`
  - **E2E**: This is the final validation. If it fails, debug using the audit trail in the logs.

---

## Quick Reference: Dependency Graph

```
Phase 1 (FTS) ──────────────────────────────────────┐
Phase 2 (Timeouts) ─────────────────────────────────┤
Phase 3 (LLM reliability) ──────────────────────────┤
Phase 4 (Batching) ──── depends on 7.1 for clean data ┤
Phase 5 (Resources) ─── 5.2 needed by 6.1, 6.3 ───┤
Phase 6 (Error handling) ── 6.4 combined with 9.1 ─┤
Phase 7 (Data quality) ─────────────────────────────┤
Phase 8 (Neo4j/Pinecone) ── 8.1 improves 4.3 perf ┤
Phase 9 (Schema) ──── depends on Phase 1 (migration chain) ┤
Phase 10 (Tests) ──── depends on ALL above ─────────┘
```

Phases 1-3 are CRITICAL and must be done in order.
Phases 4-9 can be done in listed order (some cross-dependencies noted).
Phase 10 must be last.
