# Turbo Ingestion Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable 4-account parallel ingestion of 35K cases in ~3-4 days, up from 300/day.

**Architecture:** Orchestrator (`ingestion/turbo_ingest.py`) spawns 4 subprocess workers, each running `batch_ingest_vertex.py` with its own GCP credentials. Workers share PostgreSQL/Pinecone/Neo4j. Progressive rollout (50 → 500 → 2K → remaining) with 5-layer quality defense.

**Tech Stack:** Python 3.12, asyncio, Vertex AI batch API, Pinecone, Neo4j, PostgreSQL

**Design doc:** `ingestion/TURBO_INGESTION_DESIGN.md` (single source of truth)

---

## Task 1: Make Embedding Parameters Configurable via Environment

The hardcoded embedding concurrency (semaphore=2, sub-batch=3, sleep=2.0s) is the #1 throughput bottleneck. Make these configurable so the orchestrator can tune them per-worker.

**Files:**
- Modify: `backend/app/core/providers/embeddings/gemini.py:188-204`

**Step 1: Edit embed_batch Vertex REST path to use env vars**

In `backend/app/core/providers/embeddings/gemini.py`, replace the hardcoded values in the `embed_batch` method's Vertex REST branch (lines 188-204):

```python
        if self._use_vertex_rest:
            # REST path: one content per call, limited concurrency
            # Configurable via env for turbo ingestion mode
            _SUB_BATCH = int(os.environ.get("EMBED_SUB_BATCH", "3"))
            _EMBED_SEM = int(os.environ.get("EMBED_CONCURRENCY", "2"))
            _EMBED_SLEEP = float(os.environ.get("EMBED_SLEEP", "2.0"))
            sem = asyncio.Semaphore(_EMBED_SEM)

            async def _embed_one(text: str) -> list[float]:
                async with sem:
                    return await self._vertex_rest_embed(text, task_type)

            all_results: list[list[float]] = []
            for i in range(0, len(texts), _SUB_BATCH):
                sub = texts[i : i + _SUB_BATCH]
                batch_results = await asyncio.gather(*[_embed_one(t) for t in sub])
                all_results.extend(batch_results)
                if i + _SUB_BATCH < len(texts):
                    await asyncio.sleep(_EMBED_SLEEP)
            return all_results
```

Also update the Vertex SDK path (lines 206-235) similarly:
```python
        if self._use_vertexai:
            _SUB_BATCH = int(os.environ.get("EMBED_SUB_BATCH", "3"))
            _CONCURRENCY = int(os.environ.get("EMBED_CONCURRENCY", "1"))
            _EMBED_SLEEP = float(os.environ.get("EMBED_SLEEP", "3.0"))
            sem = asyncio.Semaphore(_CONCURRENCY)
```

**Step 2: Run existing embedding tests**

Run: `cd backend && python -m pytest tests/ -k "embed" -v --timeout=30`
Expected: All existing tests PASS (env vars default to current values)

**Step 3: Commit**

```bash
git add backend/app/core/providers/embeddings/gemini.py
git commit -m "perf: make embedding concurrency configurable via env vars"
```

---

## Task 2: Make Pinecone Upsert Batch Size Configurable

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py:1097-1099`

**Step 1: Replace hardcoded 100 with env-configurable value**

At line 1097-1099 of `pipeline.py`, change:
```python
    # Upsert in batches of 100 (Pinecone recommended batch size)
    for i in range(0, len(vectors), 100):
        await vector_store.upsert(vectors[i : i + 100])
```
To:
```python
    # Upsert in batches (Pinecone recommended: 100, turbo mode: 300)
    _upsert_batch = int(os.environ.get("PINECONE_UPSERT_BATCH", "100"))
    for i in range(0, len(vectors), _upsert_batch):
        await vector_store.upsert(vectors[i : i + _upsert_batch])
```

Add `import os` at the top of the file if not already present.

**Step 2: Run pipeline tests**

Run: `cd backend && python -m pytest tests/ -k "pipeline" -v --timeout=60`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py
git commit -m "perf: make Pinecone upsert batch size configurable via env"
```

---

## Task 3: Make Database Pool Size Configurable via Environment

**Files:**
- Modify: `backend/app/core/config.py:34`

**Step 1: Make pool_size read from env**

At line 34, change:
```python
    database_pool_size: int = 30
```
To:
```python
    database_pool_size: int = int(os.environ.get("DATABASE_POOL_SIZE", "30"))
```

Note: Pydantic Settings already reads from env vars, but we want explicit `DATABASE_POOL_SIZE` support. Check if Pydantic already handles this — if the field is already mapped to `DATABASE_POOL_SIZE` env var via `model_config`, skip this step (Pydantic Settings auto-maps field names to env vars in uppercase).

**Step 2: Verify**

Run: `cd backend && python -c "from app.core.config import settings; print(settings.database_pool_size)"`
Expected: `30` (default)

**Step 3: Commit**

```bash
git add backend/app/core/config.py
git commit -m "perf: ensure database pool size is env-configurable"
```

---

## Task 4: Add Skip Community Vectors Flag

Community vectors are lowest priority and consume ~30K of the 1M Pinecone budget. Add an env flag to skip them.

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py` — find where community vectors are generated/upserted

**Step 1: Find community vector generation**

Search for "community" in `pipeline.py`. Look for the section that generates community-type vectors. Wrap it with:

```python
if not os.environ.get("SKIP_COMMUNITY_VECTORS", "").lower() in ("true", "1", "yes"):
    # existing community vector generation code
    ...
```

**Step 2: Verify with tests**

Run: `cd backend && python -m pytest tests/ -k "pipeline or ingest" -v --timeout=60`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py
git commit -m "feat: add SKIP_COMMUNITY_VECTORS env flag for Pinecone budget"
```

---

## Task 5: Add Garbage Collection to Batch Pipeline

Prevent memory buildup during long Phase 3 runs with 16GB RAM.

**Files:**
- Modify: `backend/scripts/batch_ingest_vertex.py:770-782`

**Step 1: Add gc.collect() every 50 cases**

At the top of the file, add:
```python
import gc
```

In the `_process_one` function, after the progress save block (around line 778), add:
```python
                if processed_count % 50 == 0:
                    gc.collect()
                    logger.debug("GC collected after %d cases", processed_count)
```

**Step 2: Commit**

```bash
git add backend/scripts/batch_ingest_vertex.py
git commit -m "perf: add periodic gc.collect() in Phase 3 to prevent memory buildup"
```

---

## Task 6: Add Per-Account GCS Bucket Support

Each GCP account needs its own GCS bucket. Make the bucket name configurable.

**Files:**
- Modify: `backend/scripts/batch_ingest_vertex.py:109`

**Step 1: Replace hardcoded bucket**

Change line 109:
```python
GCS_BUCKET = "smriti-batch-ingestion"
```
To:
```python
GCS_BUCKET = os.environ.get("GCS_BUCKET", "smriti-batch-ingestion")
```

Add `import os` at top if not present (it's likely already there via other imports).

**Step 2: Commit**

```bash
git add backend/scripts/batch_ingest_vertex.py
git commit -m "feat: make GCS bucket configurable via env for multi-account ingestion"
```

---

## Task 7: Add Layer 3 Quality Gate to batch_ingest_vertex.py

Between Phase 2 and Phase 3, validate metadata quality before spending on embeddings.

**Files:**
- Modify: `backend/scripts/batch_ingest_vertex.py:1411-1425`

**Step 1: Import and call quality gate**

At the top of the file, add:
```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
```

In the `run_pipeline` function, between Phase 2 and Phase 3 (around line 1418), add:

```python
        # Layer 3: Quality gate — validate metadata before Phase 3
        try:
            from ingestion.quality_gates import validate_batch_metadata
            qg_report = validate_batch_metadata(metadata_results)
            if not qg_report.passed:
                logger.error("QUALITY GATE FAILED between Phase 2 and Phase 3:")
                for f in qg_report.failures:
                    logger.error("  %s", f)
                logger.error(
                    "Fix issues and resume with: --resume %s", run_id,
                )
                continue  # Skip to next year
            else:
                logger.info("Quality gate passed: %s", qg_report.checks)
                for w in qg_report.warnings:
                    logger.warning("  QG WARNING: %s", w)
        except ImportError:
            logger.warning("quality_gates module not found, skipping Layer 3 check")
```

**Step 2: Commit**

```bash
git add backend/scripts/batch_ingest_vertex.py
git commit -m "feat: add Layer 3 metadata quality gate between Phase 2 and Phase 3"
```

---

## Task 8: Add Layer 4 Per-Case Validation to _process_single_case

**Files:**
- Modify: `backend/scripts/batch_ingest_vertex.py` — in `_process_single_case` function

**Step 1: Add validation before vector upsert**

In `_process_single_case`, after metadata merge/validation (around line 888) and before the PostgreSQL insert (line 891), add a metadata cross-contamination check. The function already has `case_id` and `metadata`.

After the line that calls `_insert_case` and before the chunking step, add a lightweight check:

```python
        # Layer 4: Per-case metadata validation
        if not metadata.title and not metadata.citation:
            logger.warning("Case %s: no title or citation, skipping", case_id)
            return "error: missing title and citation"
```

Also, after embeddings are generated (wherever `_embed_chunks` is called), add dimension check:

```python
        # Spot-check embedding dimensions
        if embeddings and len(embeddings[0]) != 1536:
            logger.error(
                "Case %s: embedding dimension %d != 1536",
                case_id, len(embeddings[0]),
            )
            return "error: wrong embedding dimension"
```

**Step 2: Commit**

```bash
git add backend/scripts/batch_ingest_vertex.py
git commit -m "feat: add Layer 4 per-case validation in Phase 3"
```

---

## Task 9: Validate Orchestrator End-to-End with --setup

**Files:**
- Test: `ingestion/turbo_ingest.py` (already written)

**Step 1: Create one test account env file**

Copy `ingestion/accounts/env_template` to `ingestion/accounts/env_a` and fill in:
- Your current GCP project name
- Path to your existing service account JSON
- Shared database credentials from `backend/.env`

**Step 2: Run setup**

```bash
cd d:/Startup/Smriti
python ingestion/turbo_ingest.py --setup
```

Expected output: Shows account status, database connectivity, Vertex AI test for account A.
Fix any FAILED items.

**Step 3: No commit needed (env files are gitignored)**

---

## Task 10: Run Trial — 50 Cases on Account A

This is the Layer 1 quality check. DO NOT PROCEED to full run until trial passes.

**Files:**
- Run: `ingestion/turbo_ingest.py --trial`

**Step 1: Run trial**

```bash
cd d:/Startup/Smriti
python ingestion/turbo_ingest.py --trial --account a --limit 50
```

This will:
1. Run Phase 1 (extract 50 cases)
2. Run Phase 2 (batch metadata — wait for completion)
3. Run Phase 3 (online processing with concurrency=2)
4. Run Layer 5 spot check
5. Print quality report

**Step 2: Review quality report**

Check `ingestion/runs/trial_a_*/quality_report.json`:
- All spot-checked cases must have PG rows, Pinecone vectors, Neo4j nodes
- Metadata fields must be populated
- No cross-contamination detected

**Step 3: Manual spot check**

Open PostgreSQL and manually verify 5 random cases:
- Does the title match the actual judgment?
- Is the year correct?
- Are acts_cited reasonable?
- Does the citation look valid?

**If trial FAILS**: Read the quality report failures, fix the issue, re-run trial.
**If trial PASSES**: Proceed to Task 11.

---

## Task 11: Set Up Remaining 3 Accounts

**Step 1: Create 3 more GCP accounts**

For each account (B, C, D):
1. Sign up at cloud.google.com with a new Gmail
2. Accept $300 free trial
3. Enable "Vertex AI API" and "Cloud Storage API"
4. Create service account: IAM → Service Accounts → Create
   - Roles: "Vertex AI User", "Storage Admin"
   - Download JSON key
5. Create GCS bucket: `gsutil mb -p PROJECT_ID gs://smriti-batch-ingestion-{b,c,d}`

**Step 2: Place credentials**

```
ingestion/accounts/account_b.json
ingestion/accounts/account_c.json
ingestion/accounts/account_d.json
```

**Step 3: Create env files**

Copy `env_template` to `env_b`, `env_c`, `env_d`. Fill in per-account values.

**Step 4: Verify all accounts**

```bash
python ingestion/turbo_ingest.py --setup
```

Expected: All 4 accounts show "OK".

---

## Task 12: Tune PostgreSQL max_connections on Hostinger

4 workers × pool_size=20 = 80 connections needed. Verify Hostinger can handle this.

**Step 1: Check current max_connections**

```sql
SHOW max_connections;
```

**Step 2: If < 100, increase it**

Edit `postgresql.conf` on Hostinger VM:
```
max_connections = 150
```
Then restart PostgreSQL: `sudo systemctl restart postgresql`

**Step 3: Verify**

```bash
python -c "
import asyncio
from app.db.postgres import async_session_factory
async def check():
    async with async_session_factory() as s:
        r = await s.execute(__import__('sqlalchemy').text('SHOW max_connections'))
        print('max_connections:', r.scalar())
asyncio.run(check())
"
```

Expected: `150` or higher.

---

## Task 13: Progressive Rollout — Small Batch (500/account)

**Step 1: Run small batch**

```bash
python ingestion/turbo_ingest.py --run --step small
```

This launches 4 workers in parallel, each processing 500 cases.
Total: 2,000 cases across 4 accounts.

**Step 2: Monitor**

In a separate terminal:
```bash
python ingestion/turbo_ingest.py --status
```

Watch for:
- Workers progressing through Phase 2 → Phase 3
- No error spikes
- Pinecone vector count growing steadily

**Step 3: Review quality report**

After all 4 workers finish, check `ingestion/runs/turbo_small_*/quality_report.json`.
All spot checks must pass.

**Step 4: Check credits spent**

Log into each GCP billing console. Expected: ~$17/account ($68 total).

---

## Task 14: Progressive Rollout — Medium Batch (2,000/account)

**Step 1: Run medium batch**

```bash
python ingestion/turbo_ingest.py --run --step medium
```

Total: 8,000 cases (cumulative: ~10,000).

**Step 2: Monitor and validate** (same as Task 13)

Expected credit spend: ~$68/account ($272 total, cumulative: ~$340).

**Step 3: Check Pinecone vector count**

Should be ~300K vectors. If approaching 900K, reduce scope.

---

## Task 15: Progressive Rollout — Full Batch (Remaining Cases)

**Step 1: Run full batch**

```bash
python ingestion/turbo_ingest.py --run --step full
```

Processes remaining ~6,200 cases per account (~24,800 total).
Cumulative: ~35,000 cases.

**Step 2: Monitor continuously**

```bash
# Watch all worker logs in real-time
tail -f ingestion/logs/worker_*.log
```

**Step 3: Final quality check**

```bash
python ingestion/turbo_ingest.py --quality-check
```

**Step 4: Retry any failures**

```bash
python ingestion/turbo_ingest.py --retry-failed
```

---

## Task 16: Final Validation & Cleanup

**Step 1: Verify final counts**

```sql
-- PostgreSQL
SELECT count(*) FROM cases WHERE ingestion_status = 'completed';
-- Should be ~35,000

SELECT count(*) FROM cases WHERE ingestion_status = 'failed';
-- Should be < 5%
```

**Step 2: Rebuild FTS index**

```bash
cd backend
python -c "
import asyncio
from scripts.ingest_s3 import _rebuild_fts_vectors
asyncio.run(_rebuild_fts_vectors())
"
```

**Step 3: Check Pinecone**

```python
# Verify vector count and types
stats = await vector_store.describe_index_stats()
print(f"Total vectors: {stats['total_vector_count']}")
# Should be < 1,000,000
```

**Step 4: Check Neo4j**

```cypher
MATCH (n) RETURN count(n);
// Should be < 200,000

MATCH ()-[r:CITES]->() RETURN count(r);
// Citation edges
```

**Step 5: Commit all code changes**

```bash
git add -A
git commit -m "feat: turbo ingestion pipeline — 4-account parallel processing for 35K cases"
```
