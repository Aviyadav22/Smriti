# Batch Ingestion Orchestrator — Design

**Date:** 2026-03-24
**Status:** Approved
**Goal:** Ingest 43K Supreme Court judgments using Gemini Batch API at 50% cost reduction and higher throughput than interactive RPD limits allow.

## Problem

Interactive Gemini API has a 1,000 RPD (requests per day) limit per project. With 5 projects, that's 5,000 cases/day — 43K cases takes ~9 days. The Gemini Batch API has separate (higher) throughput limits and costs 50% less.

## Approach: Mock LLM Provider (Option A)

**Zero modifications to any existing pipeline file.** The batch orchestrator sits entirely outside the main ingestion pipeline.

The key insight: `ingest_judgment()` calls `llm.generate_structured_from_pdf()` for metadata extraction. We create a `BatchCachedLLM` that implements the same interface but returns pre-fetched results from the Gemini Batch API. The entire existing validation/merge/regex pipeline runs untouched.

## Architecture

```
Phase 1 (submit):  PDFs → extract text → upload PDF to Files API → batch request → Gemini Batch API
Phase 2 (poll):    Poll batch jobs → download results → cache in SQLite
Phase 3 (process): Cached result → BatchCachedLLM mock → ingest_judgment() as-is → full pipeline
```

### New Files

| File | Purpose |
|------|---------|
| `backend/scripts/batch_ingest.py` | CLI with 3 subcommands: `submit`, `poll`, `process` |
| `backend/scripts/batch_llm.py` | `BatchCachedLLM` class implementing `LLMProvider` protocol |

### Existing Files Modified: NONE

## Phase 1: Submit

### CLI

```bash
python -m scripts.batch_ingest submit \
  --year-from 2015 --year-to 2023 \
  --wave-size 5000 \
  --concurrency 10
```

### Steps per wave (max 5,000 cases per wave per project)

1. Extract tar for the year (reuse `ingest_s3.extract_tar()`)
2. For each PDF in the wave:
   a. `extract_and_score(pdf_path)` → `full_text`, `TextQuality`
   b. SHA-256 text_hash dedup check against PG (skip if duplicate)
   c. Upload PDF to Gemini Files API → `file_uri`
   d. Store in `batch_state.db`: doc_key, file_uri, parquet_meta, text_hash, full_text_len, pdf_path
3. Build batch request JSONL:
   - Key: `doc_key` (normalized to forward slashes everywhere)
   - Request: `{contents: [{parts: [{file_data: {file_uri: "files/..."}}, {text: METADATA_EXTRACTION_USER}]}], systemInstruction: METADATA_EXTRACTION_SYSTEM, generationConfig: {responseMimeType: "application/json", responseSchema: METADATA_OUTPUT_SCHEMA, temperature: 0.1}}`
4. Submit via `client.batches.create(model="gemini-2.5-flash", src=jsonl_file)`
5. Store batch_job_name in `batch_jobs` table
6. Round-robin across API key projects

### Constraint Management

| Constraint | Limit | Mitigation |
|-----------|-------|------------|
| Files API 48h TTL | Files expire in 48h | Process each wave end-to-end within 48h |
| 20GB Files API/project | ~10K PDFs at 2MB avg | Wave size 5,000 per project, 5 projects available |
| Enqueued tokens (Tier 1) | 3M per project | ~214 cases per batch job; submit multiple small batches |
| doc_key normalization | Windows backslash risk | Always use forward slashes via `PurePosixPath` |

### batch_state.db Schema

```sql
CREATE TABLE batch_docs (
    doc_key TEXT PRIMARY KEY,
    year INTEGER,
    file_uri TEXT,
    text_hash TEXT,
    full_text_len INTEGER,
    parquet_meta TEXT,           -- JSON blob
    pdf_path TEXT,               -- local path for Phase 3
    api_key_index INTEGER,
    batch_job_name TEXT,
    status TEXT DEFAULT 'uploaded',  -- uploaded → submitted → completed → processed | error | batch_failed
    llm_result TEXT,             -- JSON blob from Gemini batch response
    error TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE batch_jobs (
    job_name TEXT PRIMARY KEY,
    api_key_index INTEGER,
    status TEXT DEFAULT 'pending',  -- pending → succeeded → failed
    doc_count INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);
```

## Phase 2: Poll & Collect

### CLI

```bash
python -m scripts.batch_ingest poll [--interval 60]
```

### Steps (loop until all jobs completed)

1. Query `batch_jobs WHERE status = 'pending'`
2. For each job: `client.batches.get(name=job_name)`
   - `JOB_STATE_SUCCEEDED` → download results, parse, update batch_docs
   - `JOB_STATE_FAILED` → log, mark job + docs as failed
   - Still running → skip
3. For each succeeded job:
   a. Read results (inline responses or file-based JSONL)
   b. For each result entry:
      - Match `result.key` to `batch_docs.doc_key` (exact string match)
      - **Sanity check:** result JSON must have at least `title` or `citation` — reject garbage
      - **Normalize:** unwrap batch response format to match interactive `generate_structured_from_pdf()` output (if needed — test with one case first)
      - Store raw JSON in `batch_docs.llm_result`, update `status = 'completed'`
   c. Mark batch_job `status = 'succeeded'`
4. Print summary, sleep(interval), repeat
5. Idempotent — safe to kill and restart

## Phase 3: Process

### CLI

```bash
python -m scripts.batch_ingest process \
  --year-from 2015 --year-to 2023 \
  --concurrency 20 \
  --rpm-limit 0
```

### Steps per doc (WHERE status = 'completed')

1. Load `llm_result` JSON and `parquet_meta` JSON from `batch_docs`
2. Create `BatchCachedLLM(result=llm_result)` — one per doc
3. Call `ingest_judgment()` with the mock LLM:
   ```python
   ingest_judgment(
       pdf_path=doc.pdf_path,
       parquet_metadata=json.loads(doc.parquet_meta),
       db=session,
       llm=BatchCachedLLM(json.loads(doc.llm_result)),
       embedder=real_embedder,
       vector_store=pinecone_store,
       graph_store=neo4j_store,
       storage=file_storage,
       embed_rate_limiter=embed_limiter,
   )
   ```
4. On success → `status = 'processed'`, also mark in `ingest_tracker.db`
5. On failure → `status = 'process_failed'`, store error

### Throughput (Phase 3 is embed-bound, not LLM-bound)

- LLM call is instant (cached) → no RPD/RPM constraint
- Embed API: 150 RPM/key x 5 keys = 750 RPM
- ~3 embed calls per case → ~250 cases/min → **15,000 cases/hour**
- 43K cases in **~3 hours**
- Set `--rpm-limit 0` (no LLM rate limiting needed)
- Embed rate limiter still active

## BatchCachedLLM

```python
class BatchCachedLLM:
    """LLM that returns pre-fetched Gemini Batch API results.

    Implements enough of LLMProvider for extract_metadata_llm():
    - generate_structured_from_pdf() → cached result (pipeline tries first)
    - generate_structured() → cached result (fallback path)
    - generate() → raises (not needed for metadata extraction)
    """

    def __init__(self, result: dict) -> None:
        self._result = result

    async def generate_structured_from_pdf(
        self, pdf_path, *, prompt, system, output_schema, temperature=0.1
    ) -> dict:
        return self._result

    async def generate_structured(
        self, prompt, *, system, output_schema, temperature=0.1
    ) -> dict:
        return self._result

    async def generate(self, *, prompt, system=None, **kwargs) -> str:
        raise NotImplementedError("BatchCachedLLM only supports structured generation")
```

### Critical validation

Before first production run, test with 10-20 cases:
1. Submit 10 PDFs via batch, get results
2. Compare batch result JSON structure vs interactive `generate_structured_from_pdf()` output
3. If batch wraps results differently (extra nesting, metadata), add normalization in `BatchCachedLLM`
4. Run Phase 3 on those 10 cases, verify outputs match interactive ingestion:
   - legal_propositions extracted
   - proposition vectors in Pinecone
   - case_statute_interpretations populated
   - section vectors created
   - Neo4j citation graph nodes + edges

## Operational Runbook

### Full 43K run

```bash
# Wave 1: years 2015-2017 (~12K cases)
python -m scripts.batch_ingest submit --year-from 2015 --year-to 2017 --wave-size 5000
python -m scripts.batch_ingest poll --interval 60
# Wait for all batch jobs to complete (~2-8 hours)
python -m scripts.batch_ingest process --year-from 2015 --year-to 2017 --concurrency 20

# Wave 2: years 2018-2020 (~12K cases)
python -m scripts.batch_ingest submit --year-from 2018 --year-to 2020 --wave-size 5000
python -m scripts.batch_ingest poll --interval 60
python -m scripts.batch_ingest process --year-from 2018 --year-to 2020 --concurrency 20

# Wave 3: years 2021-2023 (~19K cases)
python -m scripts.batch_ingest submit --year-from 2021 --year-to 2023 --wave-size 5000
python -m scripts.batch_ingest poll --interval 60
python -m scripts.batch_ingest process --year-from 2021 --year-to 2023 --concurrency 20

# Post-ingestion
python -m scripts.ingest_s3 rebuild-fts   # Batched FTS rebuild (500 rows/batch)
```

### Recovery

- **Phase 1 interrupted:** Re-run `submit` — SQLite tracks uploaded docs, skips already-uploaded
- **Phase 2 interrupted:** Re-run `poll` — idempotent, picks up where it left off
- **Phase 3 interrupted:** Re-run `process` — only processes `status='completed'` docs
- **Batch job failed:** Docs marked `batch_failed`, can re-submit with `--retry-failed` flag
- **Process failed for a doc:** Marked `process_failed`, can retry with `--retry-failed`

## Cost Estimate

| Item | Interactive | Batch (50% off) |
|------|-----------|-----------------|
| Gemini Flash LLM (43K calls, ~14K tokens/call) | ~$90 | **~$45** |
| Gemini Embedding (129K calls) | ~$5 | ~$5 (no batch discount) |
| **Total** | ~$95 | **~$50** |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Batch result format differs from interactive | HIGH | Test 10 cases before full run; add normalization layer |
| 48h file TTL expiry before batch completes | MEDIUM | Wave size 5K, process within 24h |
| Neo4j AuraDB connection limits at concurrency=20 | LOW | Graph failures non-blocking in pipeline; reduce concurrency if needed |
| Duplicate text extraction in Phase 3 (PDF re-read) | LOW | ~1-2s CPU per case, negligible at scale |
