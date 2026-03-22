# Pipeline Audit V2 — Complete Fix Plan

**Date**: 2026-03-21
**Scope**: 14 verified fixes across 5 severity tiers, ordered by dependency graph
**Goal**: Make the ingestion pipeline bulletproof for 35K Supreme Court cases

---

## Verification Summary

All findings were double-checked against exact line numbers. Results:
- **H10 (Stats race condition)**: FALSE POSITIVE — asyncio is single-threaded, no race
- **H8 (OCR no page limit)**: Downgraded — MAX_PAGES=5000 exists but is shared with pdfplumber; need separate MAX_OCR_PAGES
- **C2 (Global asyncio.Event)**: CONFIRMED but low-risk — Python 3.10+ Events are loop-agnostic. Still worth fixing for clarity
- **M11 (Gemini context cache TTL)**: REMOVED — dead code, never called during ingestion
- **M19 (enrichment_status CHECK)**: REMOVED — server_default='flash_only' + nullable=False means new cases always have a valid value
- **H3 (PG pool exhaustion)**: Downgraded to MEDIUM — production uses NullPool; dev pool is 25, adequate for default concurrency=10

---

## Dependency Graph

```
Phase 1: Migration chain fixes (must go first)
  Step 1.1: Fix migration 028 (ADD COLUMN IF NOT EXISTS)

Phase 2: FTS trigger overhaul (migration 030)
  Step 2.1: Add WHEN clause to FTS trigger
  Step 2.2: Remove updated_at from FTS trigger function
  Step 2.3: Add explicit updated_at to pipeline.py raw SQL

Phase 3: Ingestion script hardening (ingest_s3.py — 3 independent fixes)
  Step 3.1: Remove 660s gather timeout
  Step 3.2: Move shutdown_event inside main()
  Step 3.3: Atomic tar downloads (.tmp + rename)
  Step 3.4: Guard SIGTERM on Windows

Phase 4: Provider reliability
  Step 4.1: Add tenacity retry to GCS storage
  Step 4.2: Add Neo4j explicit transactions for batch ops
  Step 4.3: Strengthen Neo4j retry (3→5 attempts, 10→30s max)

Phase 5: Data quality fixes
  Step 5.1: Fix party_counsel field name mismatch ("name" vs "counsel_name")
  Step 5.2: Add MAX_OCR_PAGES guard (50 pages)
  Step 5.3: Add line-length heuristic to section detection

Phase 6: Schema hardening (migrations 031)
  Step 6.1: Make text_hash a unique partial index
  Step 6.2: Add ON CONFLICT (text_hash) to pipeline INSERT

Phase 7: Model sync & tests
  Step 7.1: Sync model __table_args__ with all migration indexes/constraints
  Step 7.2: Run full test suite, fix any breakage
  Step 7.3: Apply migrations to database
```

---

## Phase 1: Migration Chain Fixes

### Step 1.1: Fix migration 028 (ADD COLUMN IF NOT EXISTS)

**File**: `backend/migrations/versions/028_coram_size.py`
**Problem**: Migration 011 already adds `coram_size`. Migration 028 duplicates it. Fresh `alembic upgrade head` crashes.
**Verification**: CONFIRMED — both migrations add identical `sa.Column("coram_size", sa.Integer(), nullable=True)`

**Fix**:
```python
def upgrade() -> None:
    op.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS coram_size INTEGER")

def downgrade() -> None:
    # Don't drop — migration 011 owns this column
    pass
```

**E2E Impact**: No runtime code changes. Only affects fresh database setup or new environments.
**Tests affected**: None

---

## Phase 2: FTS Trigger Overhaul

### Step 2.1 + 2.2: New migration 030 — FTS trigger WHEN clause + remove updated_at

**File**: NEW `backend/migrations/versions/030_fts_trigger_optimization.py`
**Problem (C3)**: FTS trigger fires on ANY column update. Every `ingestion_status` or `chunk_count` update recomputes tsvector across 17 fields including `left(full_text, 500000)`. At 35K cases, bulk status updates trigger 35K unnecessary tsvector rebuilds.
**Problem (C4)**: Trigger sets `updated_at := NOW()` on every fire, breaking audit trail.
**Verification**: CONFIRMED — trigger at migration 025 has no WHEN clause, line 44 sets `NEW.updated_at := NOW()`

**Fix**: Create migration 030 that:
1. Replaces the trigger function to remove `NEW.updated_at := NOW()`
2. Drops and recreates the trigger with a WHEN clause limiting to FTS-relevant columns

The trigger function should be:
```sql
CREATE OR REPLACE FUNCTION cases_searchable_text_update()
RETURNS trigger AS $$
BEGIN
    NEW.searchable_text :=
        setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.citation, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.case_number, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.court, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(array_to_string(NEW.judge, ' '), '')), 'B') ||
        setweight(to_tsvector('english', coalesce(NEW.petitioner, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(NEW.respondent, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(NEW.headnotes, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(NEW.outcome_summary, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(NEW.description, '')), 'C') ||
        setweight(to_tsvector('english', coalesce(NEW.ratio_decidendi, '')), 'C') ||
        setweight(to_tsvector('english', coalesce(NEW.operative_order, '')), 'C') ||
        setweight(to_tsvector('english', coalesce(array_to_string(NEW.keywords, ' '), '')), 'D') ||
        setweight(to_tsvector('english', coalesce(array_to_string(NEW.acts_cited, ' '), '')), 'D') ||
        setweight(to_tsvector('english', coalesce(array_to_string(NEW.legal_principles_applied, ' '), '')), 'D') ||
        setweight(to_tsvector('english', coalesce(array_to_string(NEW.issue_classification, ' '), '')), 'D') ||
        setweight(to_tsvector('english', coalesce(left(NEW.full_text, 500000), '')), 'D');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

The trigger itself should use UPDATE OF:
```sql
DROP TRIGGER IF EXISTS cases_searchable_text_trigger ON cases;
CREATE TRIGGER cases_searchable_text_trigger
    BEFORE INSERT OR UPDATE OF
        title, citation, case_number, court, judge, petitioner, respondent,
        headnotes, outcome_summary, description, ratio_decidendi,
        operative_order, keywords, acts_cited, legal_principles_applied,
        issue_classification, full_text
    ON cases
    FOR EACH ROW
    EXECUTE FUNCTION cases_searchable_text_update();
```

**E2E Impact**:
- `pipeline.py` raw SQL UPDATEs (chunk_count, ingestion_status) will NO LONGER trigger FTS recompute → massive performance win
- `pipeline.py` raw SQL UPDATEs and INSERTs need explicit `updated_at = NOW()` since the trigger no longer sets it (Step 2.3)
- `_reconcile_orphans()` in ingest_s3.py relies on `updated_at` to find stale rows — must still work

### Step 2.3: Add explicit updated_at to pipeline.py raw SQL

**File**: `backend/app/core/ingestion/pipeline.py`
**Problem**: After removing `updated_at := NOW()` from the FTS trigger, raw SQL statements that bypass the ORM won't set `updated_at`.

**Fix**: Add `updated_at = NOW()` to these raw SQL statements:
1. The INSERT in `_insert_case()` (around line 702-811) — add `updated_at` to VALUES
2. The UPDATE at line 435-441 (`SET chunk_count = :count, ingestion_status = :status`) — add `updated_at = NOW()`
3. The UPDATE in `_record_ingestion_failure()` — add `updated_at = NOW()`
4. Any other raw SQL UPDATEs on `cases` table in pipeline.py

**E2E Impact**: Ensures `updated_at` is always current for `_reconcile_orphans()` in ingest_s3.py
**Tests affected**: `test_ingestion_pipeline.py` — check mock assertions for updated SQL strings

---

## Phase 3: Ingestion Script Hardening

### Step 3.1: Remove 660s gather timeout

**File**: `backend/scripts/ingest_s3.py` (line 851-854)
**Problem (C1)**: The `asyncio.wait_for(asyncio.gather(*workers), timeout=660.0)` wraps ALL workers for an entire year. Any year with >11 min of processing will timeout, cancel workers, and skip remaining documents. The per-document 600s timeout at line 739 is the real safety net.
**Verification**: CONFIRMED — 660s is per-year, 600s is per-document

**Fix**: Replace:
```python
await asyncio.wait_for(
    asyncio.gather(*workers, return_exceptions=True),
    timeout=660.0,
)
```
With:
```python
await asyncio.gather(*workers, return_exceptions=True)
```

**E2E Impact**: Workers will run until all documents in the year are processed (or until the per-document 600s timeout fires for individual cases). No risk of orphaned documents from premature year-level cancellation.
**Tests affected**: None

### Step 3.2: Move shutdown_event inside main()

**File**: `backend/scripts/ingest_s3.py` (lines 100-101, 104-114, 818, 830, 983)
**Problem (C2)**: `shutdown_event = asyncio.Event()` at module scope. While Python 3.10+ events are loop-agnostic, this is fragile for testing and code clarity.
**Verification**: CONFIRMED at module scope

**Fix**:
1. Remove module-level `shutdown_event = asyncio.Event()` and `_event_loop = None`
2. Create them inside `main()`:
   ```python
   async def main():
       shutdown_event = asyncio.Event()
       loop = asyncio.get_running_loop()
   ```
3. Pass `shutdown_event` to `ingest_year()` as a parameter
4. Register signal handlers inside `main()` using `loop.add_signal_handler` (Unix) or `signal.signal` (Windows)
5. Update `_worker()` and the year loop to use the passed event

**E2E Impact**: Signal handling becomes testable. No functional change in normal operation.
**Tests affected**: `test_graceful_shutdown.py` — may need to update how it creates/passes the event

### Step 3.3: Atomic tar downloads

**File**: `backend/scripts/ingest_s3.py` — `_download_with_timeout()` (line 387-392) and `_s3_download()` (line 395-431)
**Problem (C6)**: Downloads directly to the final path. Interrupted download = partial file accepted on resume.
**Verification**: CONFIRMED — only `tar_local.exists()` check, no size/integrity verification

**Fix**:
```python
def _download_with_timeout(url: str, dest: Path, timeout: int = 120) -> None:
    tmp_dest = dest.with_suffix(dest.suffix + ".tmp")
    req = urllib.request.Request(url, headers={"User-Agent": "SmritiIngest/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        with open(tmp_dest, "wb") as f:
            shutil.copyfileobj(resp, f)
    tmp_dest.rename(dest)  # atomic on same filesystem
```

**E2E Impact**: Interrupted downloads are automatically cleaned up on retry (`.tmp` file is overwritten). Resume correctly re-downloads incomplete files.
**Tests affected**: None

### Step 3.4: Guard SIGTERM on Windows

**File**: `backend/scripts/ingest_s3.py` (lines 924-925)
**Problem (C7)**: `signal.signal(signal.SIGTERM, ...)` silently fails on Windows.
**Verification**: CONFIRMED — no platform check

**Fix**:
```python
signal.signal(signal.SIGINT, _handle_shutdown)
if sys.platform != "win32":
    signal.signal(signal.SIGTERM, _handle_shutdown)
```

**E2E Impact**: None — SIGTERM was already non-functional on Windows. SIGINT (Ctrl+C) works on all platforms.
**Tests affected**: None

---

## Phase 4: Provider Reliability

### Step 4.1: Add tenacity retry to GCS storage

**File**: `backend/app/core/providers/storage/gcs_storage.py`
**Problem (H2)**: Zero retry logic. Only provider without tenacity. At 0.1% transient failure rate, ~35 documents fail unnecessarily during 35K ingestion.
**Verification**: CONFIRMED — no tenacity, no retry in entire file

**Fix**: Add tenacity retry decorator:
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

_gcs_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=retry_if_exception_type((OSError, ConnectionError, TimeoutError)),
    reraise=True,
)
```
Apply `@_gcs_retry` to `store()`, `retrieve()`, `retrieve_chunked()`, `delete()`, and `exists()`.

**E2E Impact**: GCS transient failures now auto-retry. Pipeline `except` blocks still catch after all retries exhaust.
**Tests affected**: `test_gcs_storage.py` — mock call counts may change on failure paths. Verify that tests using `side_effect=Exception(...)` still pass (tenacity will retry, so `call_count` may be 3 instead of 1).

### Step 4.2: Add Neo4j explicit transactions for batch ops

**File**: `backend/app/core/providers/graph/neo4j_store.py` — `batch_create_nodes()` (lines 332-377), `batch_create_citation_edges()` (lines 380-430)
**Problem (H1)**: Batch operations use auto-commit. Partial failure = inconsistent graph state.
**Verification**: CONFIRMED — `session.run()` without explicit transactions

**Fix**: Wrap each batch in an explicit transaction:
```python
async with self._driver.session(database=self._database) as session:
    for i in range(0, len(data), batch_size):
        batch = data[i : i + batch_size]
        async with session.begin_transaction() as tx:
            await tx.run(query, {"batch": batch})
            await tx.commit()
```

**E2E Impact**: Each batch is atomic. Failed batch = only that batch rolls back. MERGE idempotency means safe to retry.
**Tests affected**: None — existing tests mock `graph_store.query()` or use PG graph store

### Step 4.3: Strengthen Neo4j retry

**File**: `backend/app/core/providers/graph/neo4j_store.py` (lines 22-28)
**Problem**: Retry only 3 attempts / 10s max — too weak for AuraDB under bulk load.
**Verification**: CONFIRMED

**Fix**:
```python
_neo4j_retry = retry(
    stop=stop_after_attempt(5),           # was 3
    wait=wait_exponential(min=2, max=30), # was min=1, max=10
    retry=retry_if_exception_type((...)),
    reraise=True,
)
```

**E2E Impact**: Longer backoff means slower recovery but higher success rate. Total max wait: ~62s per operation (was ~11s).
**Tests affected**: None

---

## Phase 5: Data Quality Fixes

### Step 5.1: Fix party_counsel field name mismatch

**File**: `backend/app/core/ingestion/pipeline.py` (around line 1067-1069)
**Problem (H7)**: Validation checks `pc.get("name")` but graph builder uses `pc.get("counsel_name")`. Data loss.
**Verification**: CONFIRMED — metadata.py:498 uses `"name"`, pipeline.py:1067 uses `"counsel_name"`

**Fix**: Change pipeline.py to use `"name"` (matching the LLM schema and validation):
```python
# In _build_citation_graph, counsel node creation:
if isinstance(pc, dict) and pc.get("name", "").strip():
    counsel_data = {
        "name": pc.get("name", "").strip(),
        "designation": pc.get("designation", ""),
        "party": pc.get("party", ""),
    }
```

**E2E Impact**: Counsel nodes will now populate correctly in Neo4j. Previously all Counsel nodes had empty names.
**Tests affected**: `test_35k_hardening.py::test_party_counsel_invalid_filtered` — already uses `"name"`, no change needed. Check `test_pipeline_treatment.py` for counsel-related assertions.

### Step 5.2: Add MAX_OCR_PAGES guard

**File**: `backend/app/core/ingestion/pdf.py`
**Problem (H8)**: MAX_PAGES=5000 is shared for both pdfplumber (fast) and OCR (slow). A fully scanned PDF with hundreds of pages could hang for hours under full OCR.
**Verification**: PARTIALLY CONFIRMED — limit exists but is too high for OCR

**Important context**: There are TWO OCR paths:
1. `_extract_pdf_text_sync()` — per-page OCR fallback only for pages yielding <30 chars from pdfplumber. This is fine — no limit needed here since most pages in a mixed PDF won't trigger OCR.
2. `extract_with_ocr()` / `_ocr_sync()` — full-document OCR fallback. Called when the primary extraction returns very low quality. THIS needs the limit.

Many SC judgments are 100-300 pages. Major constitutional bench cases can be 500-1000+ pages. A limit of **500 pages** handles virtually all real cases while preventing multi-hour hangs on extreme outliers.

**Fix**:
```python
MAX_PAGES = 5000        # pdfplumber text extraction (fast)
MAX_OCR_PAGES = 500     # full-document OCR fallback (slow — ~3s/page at 300 DPI)
```
Apply `MAX_OCR_PAGES` only in `extract_with_ocr()` / `_ocr_sync()` — the full-document OCR path. Do NOT limit per-page OCR fallback in `_extract_pdf_text_sync()` since that only triggers on individual bad pages.

**E2E Impact**: Fully scanned PDFs >500 pages get truncated OCR (first 500 pages). At ~3s/page, 500 pages ≈ 25 min which is within the 600s per-document timeout. Log a warning when truncated.

**Post-ingestion tracking**: The `extract_with_ocr` and `_extract_pdf_text_sync` functions should return a flag indicating truncation occurred. The pipeline should propagate this up, and `ingest_s3.py` should record it in the tracker so we can query truncated cases after the full 35K run and re-process them individually with higher limits or manual OCR.

**Approach**: Add a `warnings` TEXT column to IngestTracker's `ingestion_progress` table. When OCR truncation occurs, `extract_with_ocr` should log the truncation. The pipeline returns quality info via `TextQuality` — add an `ocr_truncated` field there. The ingest script records warnings via `tracker.mark_stage(..., warnings="ocr_truncated:500/1045")`.

After the full run:
```sql
SELECT doc_key, warnings FROM ingestion_progress WHERE warnings IS NOT NULL;
```

This gives you a list of cases to re-ingest individually with a higher MAX_OCR_PAGES or manual PDF processing.

**Tests affected**: None — no tests directly test OCR paths

### Step 5.3: Add line-length heuristic to section detection

**File**: `backend/app/core/ingestion/chunker.py` — `_is_heading_position()` (lines 266-279)
**Problem (H9)**: Numbered paragraphs like "15. Evidence shows that..." are detected as EVIDENCE section boundaries. False positive rate is high at 35K docs.
**Verification**: PARTIALLY CONFIRMED — regex `[0-9]+[\.\):]` matches paragraph numbers, and bare `EVIDENCE` keyword exists in section patterns

**Fix**: Add line-length check:
```python
def _is_heading_position(text: str, match_start: int) -> bool:
    # Find the full line containing this match
    line_start = text.rfind('\n', 0, match_start) + 1
    line_end = text.find('\n', match_start)
    if line_end == -1:
        line_end = len(text)
    line_length = line_end - line_start

    # Headings are short lines; body text is long
    if line_length > 100:
        return False

    prefix = text[line_start:match_start].strip()
    if not prefix:
        return True
    if re.match(r'^(?:[IVXLC]+[\.\):]|[0-9]+[\.\):]|[A-Z][\.\)]|\([a-zA-Z0-9]+\))\s*$', prefix):
        return True
    return False
```

**E2E Impact**: Reduces false section boundaries. Chunks may be larger (fewer breaks). This changes Pinecone vectors for future ingestions — existing vectors are unaffected.
**Tests affected**: Tests for `detect_judgment_sections` or `chunk_judgment` — if any test relies on a false-positive section break, it will change. Write new test to verify the heuristic.

---

## Phase 6: Schema Hardening

### Step 6.1: Make text_hash a unique partial index (migration 031)

**File**: NEW `backend/migrations/versions/031_text_hash_unique_index.py`
**Problem (H5)**: `text_hash` has no UNIQUE constraint. Concurrent workers can insert duplicate rows for NULL-citation cases.
**Verification**: CONFIRMED — ON CONFLICT on `citation` only, SKIP LOCKED can be bypassed

**Fix**:
```sql
CREATE UNIQUE INDEX CONCURRENTLY ix_cases_text_hash_unique
ON cases (text_hash) WHERE text_hash IS NOT NULL;
```

Note: Use `CONCURRENTLY` to avoid locking the table during index creation (important for live databases).

**E2E Impact**: Duplicate inserts now fail with constraint violation instead of creating duplicate rows.

### Step 6.2: Add ON CONFLICT (text_hash) to pipeline INSERT

**File**: `backend/app/core/ingestion/pipeline.py` — `_insert_case()` INSERT statement (around line 702-811)
**Problem**: After Step 6.1, duplicate `text_hash` INSERTs will raise errors. Need to handle gracefully.

**Fix**: Add `ON CONFLICT (text_hash) WHERE text_hash IS NOT NULL DO UPDATE SET ingestion_status = EXCLUDED.ingestion_status` (or `DO NOTHING`) as a secondary conflict handler. Since PostgreSQL only allows one `ON CONFLICT` clause, restructure to use the `text_hash` unique index as the primary conflict target, with citation as a pre-check.

Alternative: Keep the existing `ON CONFLICT (citation)` and wrap the INSERT in a try/except for UniqueViolation on text_hash, treating it as a successful dedup (return existing case_id).

**E2E Impact**: Concurrent duplicate ingestion now safely deduplicates at the DB level instead of relying on SELECT-then-INSERT.
**Tests affected**: `test_concurrent_ingestion.py` — may need updating for new dedup behavior

---

## Phase 7: Model Sync & Final Tests

### Step 7.1: Sync model __table_args__ with all migration indexes/constraints

**File**: `backend/app/models/case.py` (lines 155-185)
**Problem (H4)**: 22+ indexes and 8+ CHECK constraints exist in migrations but only 17 indexes and 1 CHECK in the model. Autogenerate would try to drop them.
**Verification**: CONFIRMED — significant drift

**Fix**: Add all missing entries to `__table_args__`:
- Indexes from migrations 011, 019, 023, 029, 030, 031
- CHECK constraints from migrations 011, 022, 029

This is a model-only change with no runtime effect.

**E2E Impact**: None at runtime. Prevents destructive autogenerate.
**Tests affected**: None

### Step 7.2: Run full test suite

**Command**: `cd backend && python -m pytest tests/ -x -q`
**Expected breakage**:
- `test_gcs_storage.py` — if retry changes mock call counts
- `test_ingestion_pipeline.py` — if SQL string assertions change from Step 2.3
- `test_35k_hardening.py` — verify party_counsel test still works

### Step 7.3: Apply migrations to database

**Command**: `cd backend && set -a && source .env && set +a && python -m alembic upgrade head`
**Expected**: Migrations 030 and 031 apply cleanly.

---

## Risk Matrix

| Fix | Breaks If Done Wrong | Rollback Difficulty |
|-----|---------------------|---------------------|
| F4/F5 (FTS trigger) | FTS search broken, updated_at missing | Medium — revert migration |
| F6.1 (text_hash unique) | Duplicate existing rows block index creation | High — must dedup first |
| F8 (party_counsel) | Graph data schema change | Low — just a key name |
| F10 (section heuristic) | Different chunking = different vectors | Low — only future ingestions |
| F1 (remove gather timeout) | Runaway year processing | Low — add back if needed |

---

## Notes for Implementation Agent

1. **Read the checklist file** (`docs/plans/2026-03-21-pipeline-audit-v2-checklist.md`) before each step
2. **Read the target file(s)** before making changes — exact line numbers may shift from prior steps
3. **Run tests after each phase** — `python -m pytest tests/unit/ -x -q`
4. **Update the checklist** immediately after completing each step
5. **Migration chain**: 028 → 029 → 030 → 031 (never skip or reorder)
6. **One step at a time** — don't batch changes across phases
