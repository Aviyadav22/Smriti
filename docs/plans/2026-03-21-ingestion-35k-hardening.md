# Ingestion Pipeline 35K Hardening Plan

## Context
7-agent deep audit of the ingestion pipeline identified **7 CRITICAL, 16 HIGH, 22 MEDIUM** issues
that would cause failures, data loss, or massive slowdowns during continuous 35K case ingestion.
This plan fixes all issues in dependency order with E2E impact analysis per step.

## Architecture Constraint
All changes must preserve: existing test suite (1984 tests), Pinecone vector format,
PostgreSQL schema compatibility, Neo4j graph structure. No breaking API changes.

---

## Phase 1: Migration 025 — FTS Trigger Regression Fix
**Why first:** Migration 024 accidentally dropped `headnotes`, `outcome_summary`, `updated_at`,
and reduced `full_text` from 500K→100K. Every subsequent ingested case has degraded FTS. Must fix before any more data enters.

### Step 1.1: Create migration 025
**File:** `backend/migrations/versions/025_fix_fts_trigger_v3.py`

**Upgrade function** — `CREATE OR REPLACE FUNCTION cases_searchable_text_update()`:
- **Restore from 014:** `headnotes` (weight B), `outcome_summary` (weight B)
- **Keep from 024:** `operative_order` (C), `legal_principles_applied` (D), `issue_classification` (D)
- **Restore:** `NEW.updated_at := NOW();` before `RETURN NEW;`
- **Restore:** `LEFT(NEW.full_text, 500000)` (was 100K in 024)

**Downgrade function** — revert to migration 024's function body (exact copy).

**Complete field list for upgrade (17 fields):**
```
A: title, citation, case_number
B: court, judge[], petitioner, respondent, headnotes, outcome_summary
C: description, ratio_decidendi, operative_order
D: keywords[], acts_cited[], legal_principles_applied[], issue_classification[], full_text(500K)
```

**E2E Impact:**
- All 2 cases ingested in the E2E test have incomplete tsvectors — they need `UPDATE cases SET searchable_text = searchable_text` to re-trigger after migration
- No effect on Pinecone/Neo4j (FTS is PG-only)
- `updated_at` fix means cache invalidation works again for raw SQL paths
- Must run `UPDATE cases SET title = title WHERE TRUE;` after migration to rebuild all tsvectors

### Step 1.2: Backfill existing tsvectors
Add to the migration upgrade: a no-op UPDATE that triggers the function for all existing rows:
```sql
UPDATE cases SET title = title;
```
This fires the trigger, rebuilding `searchable_text` for every row.

---

## Phase 2: Rate Limiting & Timeouts — Prevent Cascading Failures
**Why second:** Without these, any later fix that increases throughput (batching, pool size) will
amplify rate-limit storms and hung workers. Safety nets must exist before performance work.

### Step 2.1: Add rate limiter parameter to `batch_contextualize_chunks`
**File:** `backend/app/core/ingestion/contextual_embeddings.py`

Change signature (line ~85):
```python
async def batch_contextualize_chunks(
    chunks: list[dict],
    document_metadata: dict,
    flash_llm: LLMProvider,
    document_type: str = "case_law",
    batch_size: int = 10,
    rate_limiter: AsyncRateLimiter | None = None,  # NEW
) -> list[dict]:
```

Inside `_contextualize_one()` (or the task creation loop), add:
```python
if rate_limiter:
    await rate_limiter.acquire()
```

**File:** `backend/app/core/ingestion/pipeline.py` (line ~321)
Pass the LLM rate limiter:
```python
contextualized = await batch_contextualize_chunks(
    chunk_dicts, doc_meta, fast_llm, document_type="case_law",
    rate_limiter=llm_rate_limiter,  # NEW
)
```

**E2E Impact:**
- Contextual embeddings now respect same RPM budget as metadata extraction
- Throughput per case may increase by ~30s (waiting for rate limiter between batches)
- But prevents 429 storms that currently cause cascading retries (net faster at scale)
- Tests that mock `batch_contextualize_chunks` need updated signature (add `rate_limiter=None`)

### Step 2.2: Add timeout to `GeminiEmbedder.embed_batch()`
**File:** `backend/app/core/providers/embeddings/gemini.py` (line ~86)

Wrap the API call:
```python
@_embedding_retry
async def embed_batch(self, texts: list[str]) -> list[list[float]]:
    response = await asyncio.wait_for(
        self._client.aio.models.embed_content(
            model=self._model,
            contents=texts,
            config=types.EmbedContentConfig(
                output_dimensionality=self._dimension,
            ),
        ),
        timeout=120.0,  # 2 min timeout per batch
    )
    return [e.values for e in response.embeddings]
```

Also add timeout to `embed_text()`:
```python
@_embedding_retry
async def embed_text(self, text: str) -> list[float]:
    response = await asyncio.wait_for(
        self._client.aio.models.embed_content(...),
        timeout=60.0,
    )
```

**E2E Impact:**
- Hung embedding calls now fail after 120s instead of hanging forever
- The `_embedding_retry` decorator (5 attempts) will retry on `asyncio.TimeoutError`
- Pipeline's `_embed_chunks` already has a 300s outer timeout (line ~333) — this inner timeout ensures individual batches fail fast
- No test changes needed (mock calls return immediately)

### Step 2.3: Add per-worker timeout in `ingest_s3.py`
**File:** `backend/scripts/ingest_s3.py` (line ~673)

Wrap `ingest_judgment()` call:
```python
try:
    case_id = await asyncio.wait_for(
        ingest_judgment(str(pdf_path), parquet_meta, db=db, ...),
        timeout=600.0,  # 10 min max per case
    )
except asyncio.TimeoutError:
    logger.error("Timeout after 600s for %s", doc_key)
    await asyncio.to_thread(tracker.mark_failed, doc_key, "timeout_600s", increment_retry=True)
    stats["failed"] += 1
    return
```

**E2E Impact:**
- Prevents permanently hung workers (was CRITICAL)
- 600s is generous (typical case takes 60-120s, 500-page cases take 300-400s)
- `mark_failed` with `increment_retry=True` means the case will be retried (up to 3x)
- Shutdown now completes in bounded time

### Step 2.4: Add timeout to `asyncio.gather` in shutdown
**File:** `backend/scripts/ingest_s3.py` (line ~770)

```python
try:
    await asyncio.wait_for(
        asyncio.gather(*workers, return_exceptions=True),
        timeout=660.0,  # 10 min worker timeout + 60s grace
    )
except asyncio.TimeoutError:
    logger.warning("Workers did not complete within 660s after shutdown signal")
    for w in workers:
        w.cancel()
```

**E2E Impact:**
- SIGINT/SIGTERM now guaranteed to complete within ~11 minutes
- Combined with Step 2.3's per-case timeout, workers should finish current case within 600s
- Cancelled workers' in-progress cases remain as `ingestion_status = 'processing'` (cleaned up by Step 6.3)

---

## Phase 3: LLM Reliability — Truncation, Null Detection, Retry Simplification
**Why third:** Now that rate limits and timeouts exist, fix the LLM interaction layer
so metadata extraction is reliable and cost-efficient.

### Step 3.1: Add text truncation in `extract_metadata_llm()`
**File:** `backend/app/core/ingestion/metadata.py`

Add helper at module level:
```python
_HEAD_CHARS = 30_000
_TAIL_CHARS = 20_000

def _truncate_for_llm(text: str) -> str:
    """Head+tail truncation to stay within LLM context budget."""
    if len(text) <= _HEAD_CHARS + _TAIL_CHARS:
        return text
    return (
        text[:_HEAD_CHARS]
        + "\n\n[...middle section truncated for length...]\n\n"
        + text[-_TAIL_CHARS:]
    )
```

Use in the text-fallback path (line ~198):
```python
truncated = _truncate_for_llm(text)
prompt = METADATA_EXTRACTION_USER.format(judgment_text=truncated)
```

**E2E Impact:**
- 5-10% of SC judgments exceed 50K chars — these now reliably extract metadata
- Cost reduction: ~30% for long documents
- Quality: head captures title/citation/headnotes, tail captures operative order/conclusion
- PDF multimodal path unaffected (Gemini handles full PDF natively)
- Chunking still uses full `full_text` (truncation only for metadata LLM call)

### Step 3.2: Fix all-null response detection
**File:** `backend/app/core/ingestion/metadata.py` (line ~207)

Replace:
```python
if not result:
    raise RuntimeError("LLM returned empty structured output")
```
With:
```python
if not result or all(v is None for v in result.values()):
    raise RuntimeError("LLM returned empty/all-null structured output")
```

**E2E Impact:**
- Catches `{"title": null, "year": null, ...}` responses (estimated 1-2% of cases)
- RuntimeError triggers retry (was made retryable in previous session)
- No false positives: a response with even one non-null field passes through

### Step 3.3: Remove inner retry loop in `extract_metadata_llm`
**File:** `backend/app/core/ingestion/metadata.py`

Currently there are 3 retry layers:
1. Gemini provider: tenacity 5x (transport-level)
2. `extract_metadata_llm`: manual `for attempt in range(max_retries)` 3x
3. Pipeline: tenacity 3x wrapper around `extract_metadata_llm`

Remove layer 2 (the manual for-loop). Keep layers 1 and 3.

Restructure `extract_metadata_llm` to be a single-attempt function:
- Remove the `for attempt in range(max_retries)` loop
- Remove the `max_retries` parameter
- Remove the manual `asyncio.sleep(backoff)` between retries
- Let exceptions propagate to the pipeline's tenacity decorator

**E2E Impact:**
- Max attempts: 5 (Gemini) × 3 (pipeline) = 15 (was 5 × 3 × 3 = 45)
- Worst-case per-case retry time: ~5 min (was ~15 min)
- Simpler code, easier to reason about retry behavior
- Tests that mock `max_retries` parameter need updating
- `test_metadata_llm_retry.py` needs rewrite (currently tests the inner retry loop)

---

## Phase 4: Batching & Performance — Reduce DB/Graph Round-trips
**Why fourth:** With reliability fixed, optimize throughput. These changes reduce
per-case DB calls from ~75 to ~10.

### Step 4.1: Bulk INSERT for `_persist_sections`
**File:** `backend/app/core/ingestion/pipeline.py` (line ~1178)

Replace the for-loop with a single executemany:
```python
async def _persist_sections(db, case_id: str, sections: list) -> None:
    if not sections:
        return
    params = [
        {
            "id": str(uuid.uuid4()),
            "case_id": str(case_id),
            "section_type": section.type,
            "content": section.text,
            "section_index": idx,
        }
        for idx, section in enumerate(sections)
    ]
    await db.execute(
        text(
            "INSERT INTO case_sections (id, case_id, section_type, content, section_index) "
            "VALUES (:id, :case_id, :section_type, :content, :section_index) "
            "ON CONFLICT DO NOTHING"
        ),
        params,  # SQLAlchemy executemany with list of dicts
    )
```

**E2E Impact:**
- 50 round-trips → 1 for a typical case
- 35K cases × 50 sections avg = 1.75M → 35K DB calls
- No schema change, same ON CONFLICT behavior
- Must verify SQLAlchemy `text()` + list-of-dicts produces executemany (it does with asyncpg)

### Step 4.2: Bulk INSERT for `_persist_citation_equivalents`
**File:** `backend/app/core/ingestion/pipeline.py` (line ~1201)

Same pattern as Step 4.1. Replace for-loop with executemany.

**E2E Impact:** Same as 4.1 but for citation equivalents (~5 per case avg).

### Step 4.3: Batch Neo4j V2 enrichment with UNWIND
**File:** `backend/app/core/ingestion/pipeline.py` (line ~1044)

Replace per-item loops with UNWIND queries:

**Citation treatments** (replace for-loop at ~1045):
```python
if metadata.citation_treatments:
    ct_data = [
        {"fragment": ct.get("cited_case", "")[:50], "context": ct.get("context", ""), "paragraph": ct.get("paragraph", "")}
        for ct in metadata.citation_treatments if ct.get("cited_case")
    ]
    if ct_data:
        await graph_store.query(
            "UNWIND $treatments AS t "
            "MATCH (a:Case {id: $case_id})-[r:CITES]->(b:Case) "
            "WHERE b.citation CONTAINS t.fragment "
            "SET r.context = t.context, r.paragraph = t.paragraph",
            params={"case_id": case_id, "treatments": ct_data},
        )
```

**Counsel nodes** (replace for-loop at ~1069):
```python
if metadata.party_counsel:
    counsel_data = [{"name": c.get("name", ""), "designation": c.get("designation", "")} for c in metadata.party_counsel if c.get("name")]
    if counsel_data:
        await graph_store.query(
            "UNWIND $counsel AS c "
            "MERGE (cn:Counsel {name: c.name}) "
            "WITH cn, c MATCH (case:Case {id: $case_id}) "
            "MERGE (cn)-[:REPRESENTED_IN {designation: c.designation}]->(case)",
            params={"case_id": case_id, "counsel": counsel_data},
        )
```

**Legal principles** (replace for-loop at ~1085):
```python
if metadata.legal_principles_applied:
    await graph_store.query(
        "UNWIND $principles AS p "
        "MERGE (lp:LegalPrinciple {name: p}) "
        "WITH lp MATCH (case:Case {id: $case_id}) "
        "MERGE (case)-[:APPLIES_PRINCIPLE]->(lp)",
        params={"case_id": case_id, "principles": metadata.legal_principles_applied},
    )
```

**Issue classification** (replace for-loop at ~1099):
```python
if metadata.issue_classification:
    await graph_store.query(
        "UNWIND $issues AS i "
        "MERGE (issue:Issue {tag: i}) "
        "WITH issue MATCH (case:Case {id: $case_id}) "
        "MERGE (case)-[:CLASSIFIED_AS]->(issue)",
        params={"case_id": case_id, "issues": metadata.issue_classification},
    )
```

**E2E Impact:**
- ~22 individual Neo4j queries per case → ~4 UNWIND queries
- 35K cases: 770K → 140K Neo4j queries (5.5x reduction)
- MERGE behavior preserved (idempotent)
- Must ensure UNWIND with empty list is a no-op (it is in Cypher)
- Neo4j constraints needed for Counsel/LegalPrinciple/Issue nodes (Step 8.1)

---

## Phase 5: Resource Management — Disk, Connections, Thread Safety
**Why fifth:** Performance improvements from Phase 4 will increase concurrency pressure.
Fix resource management before scaling up.

### Step 5.1: Clean up PDFs after processing
**File:** `backend/scripts/ingest_s3.py`

After successful `ingest_judgment()` in `_process_one()` (line ~685), delete the PDF:
```python
try:
    pdf_path.unlink(missing_ok=True)
except OSError:
    pass  # Non-critical, log at DEBUG
```

After `ingest_year()` completes all cases for a year, delete the tar and extracted dir:
```python
# After all cases processed for this year
import shutil
tar_path.unlink(missing_ok=True)
if extract_dir.exists():
    shutil.rmtree(extract_dir, ignore_errors=True)
```

**E2E Impact:**
- Disk usage: ~140GB → ~5GB peak (only current year's tar + in-flight PDFs)
- Must not delete before `ingest_judgment` completes (PDF needed for multimodal)
- Failed cases: PDF deleted but case can be re-downloaded on retry (tar re-extracted)

### Step 5.2: Increase PG pool size to match concurrency
**File:** `backend/app/core/config.py` (line ~34)

```python
database_pool_size: int = 15  # was 5
database_max_overflow: int = 10  # keep at 10
```

Total: 25 connections (supports concurrency=10 + overhead for failure recording, status updates).

**E2E Impact:**
- Prevents pool timeout cascades with 10 concurrent workers
- Supavisor (prod) still limits actual connections — this sets the local pool ceiling
- No effect on tests (tests use in-memory SQLite or small pool)

### Step 5.3: Add threading.Lock to IngestTracker
**File:** `backend/scripts/ingest_s3.py` (line ~109)

```python
def __init__(self, db_path: Path = TRACKER_DB) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
    self._conn.execute("PRAGMA journal_mode=WAL")
    self._lock = threading.Lock()  # NEW
    self._migrate_schema()
```

Wrap all write methods with the lock:
```python
def mark_success(self, doc_key: str) -> None:
    with self._lock:
        self._conn.execute(...)
        self._conn.commit()

def mark_failed(self, doc_key: str, error: str, ...) -> None:
    with self._lock:
        ...

def mark_stage(self, doc_key: str, stage: str) -> None:
    with self._lock:
        ...
```

Read methods (`is_processed`, `detailed_stats`) also need the lock for consistency.

**E2E Impact:**
- Prevents "database is locked" errors with 10 concurrent workers
- Slight serialization overhead (~microseconds per lock acquire)
- No effect on tests (tests don't use concurrent tracker access)

---

## Phase 6: Error Handling & Resilience
**Why sixth:** With resources properly managed, fix error handling so failures
are correctly recorded and orphans are cleaned up.

### Step 6.1: Fix `_record_ingestion_failure` — use separate session
**File:** `backend/app/core/ingestion/pipeline.py` (line ~828)

Change `_record_ingestion_failure` to create its own session:
```python
async def _record_ingestion_failure(
    case_id: str, pdf_path: str, error_msg: str,
) -> None:
    """Record failure using a fresh session (broken pipeline session may be unusable)."""
    try:
        async with async_session_factory() as fresh_db:
            await fresh_db.execute(
                text("UPDATE cases SET ingestion_status = 'failed' WHERE id = :id"),
                {"id": case_id},
            )
            await fresh_db.execute(
                text("INSERT INTO audit_log (case_id, action, detail) VALUES (:cid, 'ingestion_failed', :detail)"),
                {"cid": case_id, "detail": error_msg[:500]},
            )
            await fresh_db.commit()
    except Exception as exc:
        logger.error("Failed to record ingestion failure for %s: %s", case_id, exc)
```

Update callers (lines ~510, ~498-505) to not pass `db` parameter.

**E2E Impact:**
- Failure recording now works even when the pipeline session is broken
- Uses an additional PG connection briefly (Step 5.2 increased pool size)
- audit_log entries now reliably created for post-mortem analysis
- Must add `from app.db.postgres import async_session_factory` import if not present

### Step 6.2: Add startup API key validation
**File:** `backend/scripts/ingest_s3.py`

Add after key pool build (line ~610):
```python
async def _validate_api_keys(llm_pool: list[GeminiLLM]) -> list[int]:
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
```

Call before starting workers. If ALL keys are bad, abort. If some are bad, warn and continue with valid keys.

**E2E Impact:**
- Fail fast instead of discovering bad keys hours into ingestion
- Small cost: 1 minimal API call per key (~0.001 cents each)
- Must handle the case where `generate` method signature differs (check LLMProvider protocol)

### Step 6.3: Add startup reconciliation for orphaned 'processing' rows
**File:** `backend/scripts/ingest_s3.py`

Add at the start of `ingest_year()` or the main `run()` function:
```python
async def _reconcile_orphans() -> int:
    """Reset cases stuck in 'processing' from a crashed run."""
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
```

**E2E Impact:**
- Crashed runs no longer leave phantom 'processing' rows
- 1-hour threshold prevents resetting actively-being-processed cases
- These cases will be retried on next run (tracker has them as incomplete)

### Step 6.4: Fix `ingestion_status` default to 'pending'
**File:** `backend/app/models/case.py` (line ~60)

```python
ingestion_status: Mapped[str] = mapped_column(
    sa.String(20), nullable=False, server_default="pending"  # was "complete"
)
```

**File:** New migration `026_fix_ingestion_status_default.py`:
```sql
ALTER TABLE cases ALTER COLUMN ingestion_status SET DEFAULT 'pending';
```

**E2E Impact:**
- New rows without explicit status start as 'pending' (correct)
- Existing rows unaffected (already have explicit values)
- Pipeline already sets status explicitly — this is a safety net
- Migration is tiny (single ALTER)

---

## Phase 7: Data Quality — Validation & Cleaning
**Why seventh:** Core reliability is fixed. Now improve data quality for the 35K run.

### Step 7.1: Add V2 field validation in `validate_with_regex()`
**File:** `backend/app/core/ingestion/metadata.py`

Add after existing validation (~line 449):
```python
# --- V2 Field Validation ---
# judicial_tone enum
valid_tones = {"formal", "assertive", "sympathetic", "critical", "neutral", "analytical"}
if meta.judicial_tone and meta.judicial_tone.lower() not in valid_tones:
    meta.judicial_tone = None

# filing_date — validate ISO format
if meta.filing_date and not _parse_date_str(meta.filing_date):
    meta.filing_date = None

# hearing_count — sanity range
if meta.hearing_count is not None and (meta.hearing_count < 0 or meta.hearing_count > 500):
    meta.hearing_count = None

# operative_order length cap
if meta.operative_order and len(meta.operative_order) > 10_000:
    meta.operative_order = meta.operative_order[:10_000]

# List fields — ensure lists, dedup, cap length
_V2_LIST_FIELDS = {
    "arguments_raised": 50, "key_observations": 30, "citation_treatments": 100,
    "distinguished_cases": 50, "overruled_cases": 50, "legal_principles_applied": 30,
    "procedural_history": 30, "interim_orders": 20, "urgency_indicators": 10,
    "party_counsel": 30, "issue_classification": 20, "fact_pattern_tags": 20,
    "conditions_imposed": 20,
}
for field_name, max_items in _V2_LIST_FIELDS.items():
    val = getattr(meta, field_name, None)
    if val is not None:
        if not isinstance(val, list):
            setattr(meta, field_name, [val] if val else [])
            val = getattr(meta, field_name)
        if len(val) > max_items:
            setattr(meta, field_name, val[:max_items])

# citation_treatments — validate dict structure
if meta.citation_treatments:
    valid_treatments = []
    for ct in meta.citation_treatments:
        if isinstance(ct, dict) and ct.get("cited_case"):
            valid_treatments.append(ct)
    meta.citation_treatments = valid_treatments

# party_counsel — validate dict structure
if meta.party_counsel:
    valid_counsel = []
    for pc in meta.party_counsel:
        if isinstance(pc, dict) and pc.get("name"):
            valid_counsel.append(pc)
    meta.party_counsel = valid_counsel
```

**E2E Impact:**
- LLM hallucinations in V2 fields now caught before DB insert
- Invalid `judicial_tone` values don't corrupt analytics
- Oversized lists capped (prevents PG array bloat)
- citation_treatments with missing keys filtered (prevents Neo4j graph errors in Step 4.3)

### Step 7.2: Extend editorial regex for SCC/AIR/SCALE/MANU reporters
**File:** `backend/app/core/ingestion/pdf.py` (line ~76)

Add to `_REPORTER_PAGE_MARKER_RE`:
```python
_REPORTER_PAGE_MARKER_RE = re.compile(
    # Existing SCR patterns
    r"^\s*\[?\d{4}\]?\s+\d+\s+S\.?\s*C\.?\s*R\.?\s+\d+\s*$|"
    r"^\s*\d+\s+\[?\d{4}\]?\s+\d+\s+S\.?\s*C\.?\s*R\.?\s*$|"
    # SCC: (2024) 5 SCC 123 or (2024) 5 SCC (Cri) 123
    r"^\s*\(\d{4}\)\s+\d+\s+SCC\s+(?:\([A-Za-z]+\)\s+)?\d+\s*$|"
    # AIR: AIR 2024 SC 123
    r"^\s*AIR\s+\d{4}\s+SC\s+\d+\s*$|"
    # SCALE: (2024) 3 SCALE 456
    r"^\s*\(\d{4}\)\s+\d+\s+SCALE\s+\d+\s*$|"
    # MANU: MANU/SC/1234/2024
    r"^\s*MANU/\w+/\d+/\d{4}\s*$",
    re.MULTILINE,
)
```

**E2E Impact:**
- SCC-sourced PDFs (most common reporter) now have page markers stripped
- Prevents reporter noise in embeddings and FTS
- No false positives (patterns require standalone lines with specific format)
- Existing editorial filter tests need new parametrized cases

### Step 7.3: Add control character stripping
**File:** `backend/app/core/ingestion/pdf.py` — in `clean_extracted_text()` after NFKC normalization

```python
# Strip control characters (except \n, \t, \r)
text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
```

**E2E Impact:**
- Prevents JSON serialization errors in downstream Pinecone metadata
- Prevents PostgreSQL insertion failures on NUL bytes
- Preserves newlines and tabs (essential for text structure)

---

## Phase 8: Neo4j & Pinecone Optimization
**Why eighth:** Phase 4's UNWIND queries need Neo4j constraints to be fast.

### Step 8.1: Add Neo4j unique constraints for V2 node types
**File:** `backend/app/core/providers/graph/neo4j_store.py` — in `ensure_constraints()` (line ~200)

Add:
```python
("constraint_counsel_name_unique",
 "CREATE CONSTRAINT constraint_counsel_name_unique IF NOT EXISTS "
 "FOR (c:Counsel) REQUIRE c.name IS UNIQUE"),
("constraint_principle_name_unique",
 "CREATE CONSTRAINT constraint_principle_name_unique IF NOT EXISTS "
 "FOR (p:LegalPrinciple) REQUIRE p.name IS UNIQUE"),
("constraint_issue_tag_unique",
 "CREATE CONSTRAINT constraint_issue_tag_unique IF NOT EXISTS "
 "FOR (i:Issue) REQUIRE i.tag IS UNIQUE"),
```

**E2E Impact:**
- MERGE queries from Step 4.3 now use index lookups instead of label scans
- At 35K cases: 350K LegalPrinciple MERGE operations go from O(n) scan to O(1) lookup
- Constraints are `IF NOT EXISTS` — safe to run multiple times
- Must run `ensure_constraints()` before ingestion (already called at startup)

### Step 8.2: Configure Neo4j connection pool explicitly
**File:** `backend/app/core/providers/graph/neo4j_store.py` (line ~70)

```python
self._driver = AsyncGraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_user, settings.neo4j_password),
    max_connection_pool_size=30,  # NEW (was default 50, reduce for AuraDB free tier)
    connection_acquisition_timeout=30.0,  # NEW
)
```

**E2E Impact:**
- Explicit pool prevents connection exhaustion on AuraDB free tier (25-50 limit)
- 30 connections supports 10 workers × ~3 concurrent queries without exhaustion
- acquisition_timeout gives clear error instead of indefinite hang

---

## Phase 9: Schema Hardening
**Why ninth:** All functional fixes done. Add DB constraints and indexes for data integrity at 35K.

### Step 9.1: Create migration 026 for schema improvements
**File:** `backend/migrations/versions/026_schema_hardening.py`

Note: Combine with Step 6.4's ingestion_status default change.

```python
def upgrade() -> None:
    # Fix ingestion_status default
    op.execute("ALTER TABLE cases ALTER COLUMN ingestion_status SET DEFAULT 'pending'")

    # CHECK constraint on enrichment_status
    op.execute(
        "ALTER TABLE cases ADD CONSTRAINT ck_cases_enrichment_status "
        "CHECK (enrichment_status IN ('flash_only', 'pro_enriched', 'failed'))"
    )

    # Missing index on author_judge
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cases_author_judge "
        "ON cases (author_judge) WHERE author_judge IS NOT NULL"
    )

    # Composite index for court + decision_date queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cases_court_decision_date "
        "ON cases (court, decision_date DESC)"
    )
```

**E2E Impact:**
- `enrichment_status` CHECK prevents invalid values at DB level
- `author_judge` index enables fast judge analytics queries
- `court + decision_date` composite index speeds up "recent cases from X court" queries
- All `IF NOT EXISTS` / `ADD CONSTRAINT` — safe to run multiple times

---

## Phase 10: Tests & Verification

### Step 10.1: New and updated tests

**New file:** `backend/tests/unit/test_35k_hardening.py`
Tests for:
- `_truncate_for_llm()` — short text passes through, long text truncated
- All-null detection — `{"title": null}` raises RuntimeError
- V2 field validation — invalid judicial_tone → None, oversized lists capped
- Bulk section INSERT — verify executemany produces correct rows
- Neo4j UNWIND queries — mock graph_store, verify single query per type
- Per-worker timeout — verify TimeoutError is caught and recorded
- SQLite lock — verify concurrent writes don't raise "database is locked"
- Control char stripping — NUL bytes removed, newlines preserved
- Extended editorial regex — SCC/AIR/SCALE/MANU patterns matched

**Updated tests:**
- `test_metadata_llm_retry.py` — remove inner retry loop tests, verify pipeline-level retry
- `test_editorial_filters.py` — add SCC/AIR/SCALE/MANU parametrized cases
- Any test that calls `batch_contextualize_chunks` — add `rate_limiter=None` kwarg

### Step 10.2: Run full test suite
```bash
cd backend && python -m pytest tests/unit/ --tb=short -q
```
Must pass with 0 failures.

### Step 10.3: Apply migrations and run E2E ingestion test
```bash
cd backend && PYTHONPATH=. alembic upgrade head
python scripts/ingest_s3.py run --year 2020 --limit 3
```

Verify:
1. FTS search finds headnotes/outcome_summary content
2. `updated_at` changes on each UPDATE
3. No hung workers (complete within 10 min)
4. PDFs cleaned up after processing
5. V2 fields validated (no garbage in citation_treatments)
6. Neo4j constraints exist for Counsel/LegalPrinciple/Issue
7. `ingestion_status` default is 'pending' for new inserts

---

## Files Modified (Complete List)

| File | Changes |
|------|---------|
| `backend/migrations/versions/025_fix_fts_trigger_v3.py` | NEW — FTS trigger with all fields |
| `backend/migrations/versions/026_schema_hardening.py` | NEW — constraints, indexes, defaults |
| `backend/app/core/ingestion/contextual_embeddings.py` | Add `rate_limiter` parameter |
| `backend/app/core/providers/embeddings/gemini.py` | Add timeouts to embed_batch/embed_text |
| `backend/scripts/ingest_s3.py` | Worker timeout, PDF cleanup, shutdown timeout, key validation, orphan reconciliation, SQLite lock |
| `backend/app/core/ingestion/metadata.py` | Text truncation, all-null check, remove inner retry, V2 validation |
| `backend/app/core/ingestion/pipeline.py` | Bulk sections INSERT, bulk citations INSERT, batched Neo4j V2, fix failure recording |
| `backend/app/core/ingestion/pdf.py` | Extended editorial regex, control char stripping |
| `backend/app/core/providers/graph/neo4j_store.py` | V2 constraints, explicit pool config |
| `backend/app/core/config.py` | Increase pool_size to 15 |
| `backend/app/models/case.py` | Fix ingestion_status default |
| `backend/tests/unit/test_35k_hardening.py` | NEW — comprehensive tests for all changes |
| `backend/tests/unit/test_metadata_llm_retry.py` | Update for removed inner retry |
| `backend/tests/unit/test_editorial_filters.py` | Add SCC/AIR/SCALE/MANU cases |

## Cross-Cutting E2E Impact Matrix

| Change | FTS | Pinecone | Neo4j | PG Perf | Reliability | Cost |
|--------|-----|----------|-------|---------|-------------|------|
| Migration 025 (FTS fix) | FIX | - | - | +rebuild | - | - |
| Rate limiter (contextual) | - | - | - | - | FIX | +30s/case |
| Embed timeout | - | - | - | - | FIX | - |
| Worker timeout | - | - | - | - | FIX | - |
| Text truncation | - | - | - | - | FIX | -30% |
| All-null detection | - | - | - | - | FIX | - |
| Remove inner retry | - | - | - | - | SIMPLIFY | -70% retry time |
| Bulk sections | - | - | - | -97% calls | - | - |
| Bulk citations | - | - | - | -80% calls | - | - |
| Neo4j UNWIND | - | - | -80% calls | - | - | - |
| PDF cleanup | - | - | - | - | FIX disk | - |
| PG pool size | - | - | - | FIX pool | FIX | - |
| SQLite lock | - | - | - | - | FIX | - |
| Failure recording | - | - | - | - | FIX audit | - |
| Key validation | - | - | - | - | FIX startup | - |
| Orphan reconciliation | - | - | - | - | FIX orphans | - |
| V2 validation | - | FIX meta | FIX meta | - | FIX | - |
| Editorial regex | FIX noise | FIX noise | - | - | - | - |
| Control chars | - | FIX JSON | - | FIX insert | - | - |
| Neo4j constraints | - | - | FIX perf | - | - | - |
| Schema hardening | - | - | - | FIX queries | FIX | - |
