# Chapter 9: Scaling the Mountain

---

Building Smriti with 100 test cases was one thing. Ingesting **35,000** Supreme Court judgments — each one needing text extraction, LLM metadata extraction, chunking, embedding, and graph building — was a completely different beast.

This chapter is about scaling up, the mistakes made along the way, and the clever solution that cut costs in half.

---

## The Original Pipeline: One at a Time

The first ingestion script (`ingest_s3.py`) processed cases one by one:

```
For each case:
  1. Download PDF from S3
  2. Extract text (+ OCR fallback)
  3. Call Gemini for metadata extraction
  4. Validate with regex
  5. Chunk the text
  6. Generate embeddings (Gemini API)
  7. Upsert vectors to Pinecone
  8. Build citation graph in Neo4j
  9. Update PostgreSQL

Repeat 35,000 times.
```

At roughly 30-60 seconds per case (mostly waiting for API calls), that's **12-25 days** of continuous processing. And if it crashes halfway through? Start over.

---

## Making It Robust

The script evolved through several iterations to handle the harsh realities of bulk processing:

### Queue-Based Workers
Instead of sequential processing, cases go into an async queue. Multiple workers pull from the queue and process in parallel. Configurable concurrency — 5 workers, 10 workers, whatever the API rate limits allow.

### SQLite Progress Tracker
Every case's progress is tracked in a local SQLite database:

```sql
ingestion_progress:
  case_id TEXT PRIMARY KEY
  stage_extracted BOOLEAN    -- text extraction done?
  stage_metadata BOOLEAN     -- LLM metadata done?
  stage_embedded BOOLEAN     -- vectors generated?
  stage_stored BOOLEAN       -- Pinecone upserted?
  stage_graphed BOOLEAN      -- Neo4j updated?
  warnings TEXT[]
  retry_count INTEGER
```

If the script crashes at case #15,432, restart it. It reads the SQLite database, sees that 15,431 cases are complete, and picks up from #15,432.

### Circuit Breaker
If 10 consecutive cases fail (API down, rate limit hit, network issues), the script **stops automatically**. No point burning through rate limits on a broken connection.

### Graceful Shutdown
Press Ctrl+C and the script doesn't just die. It:
1. Stops pulling new cases from the queue
2. Waits for in-progress cases to finish
3. Saves checkpoint to SQLite
4. Exits cleanly

### Rate Limiter Pool
The Gemini API has rate limits. The script maintains a `RateLimiterPool` that distributes API calls across configured keys, respecting per-key limits.

---

## The Batch API Saga: A Cautionary Tale

Processing 35,000 cases one-at-a-time, even with parallelism, meant 35,000 individual Gemini API calls for metadata extraction alone. At $0.002 per call, that's $70 — and slow.

Google offers a **Batch API** that processes many requests at once at 50% the price. Sounds perfect!

### Attempt 1: Google AI Studio Batch (FAILED)

Avi's first attempt used the AI Studio Batch API. It almost worked. But then:

**Problem 1**: AI Studio batch does NOT support `responseSchema` in JSONL requests. Without structured output, Gemini returns freeform text instead of clean JSON. The metadata quality dropped dramatically — hallucinated fields, missing data, wrong formats.

**Problem 2**: On Tier 1 (free tier), only Gemini Pro models process batch jobs. Flash models (cheaper, which is the whole point) stay in `PENDING` status forever.

**Problem 3**: AI Studio batch doesn't support `systemInstruction` in JSONL. No system prompt = no extraction rules = garbage output.

After days of debugging, Avi made a decision:

> **ADR-020**: AI Studio Batch API is NOT suitable for metadata extraction. Do not use it.

The old batch scripts (`batch_ingest.py`, `batch_llm.py`, `batch_state.py`) were deprecated. Lessons learned.

### Attempt 2: Vertex AI Batch (SUCCESS!)

Vertex AI is Google's enterprise ML platform. Its Batch API is completely different from AI Studio's:

- ✅ Supports `responseSchema` (structured JSON output)
- ✅ Supports `systemInstruction` (system prompts work)
- ✅ Supports PDF multimodal (send actual PDFs, not just text)
- ✅ 50% cost discount on batch pricing
- ✅ Works with Flash models

The catch? Vertex AI requires a Google Cloud project with billing. But the 50% cost savings more than justify it.

---

## The Vertex AI Batch Pipeline

The production ingestion pipeline is a **4-phase hybrid** — batch for the expensive LLM step, online for everything else:

### Phase 1: Text Extraction + GCS Upload (~5 min per 1,000 cases)

```
For each case:
  1. Download PDF from S3 (HTTPS, no AWS CLI needed)
  2. Extract text (PyMuPDF + OCR fallback)
  3. Compute text_hash (SHA-256) for dedup
  4. Upload text to Google Cloud Storage
  5. Add to manifest: {case_id, gcs_uri, text_hash}
```

All local processing — fast and cheap. The GCS upload is for Phase 2.

### Phase 2: Batch Metadata Extraction (~30 min wait)

```
1. Build JSONL file:
   Each line = {
     pdf_uri: "gs://smriti-batch-ingestion/case_123.txt",
     prompt: "Extract metadata from this judgment...",
     system: "You are a legal metadata extraction system...",
     output_schema: { title: str, citation: str, ... }
   }

2. Submit to Vertex AI Batch API
   → Model: gemini-2.5-flash (NOT preview — previews aren't on Vertex)
   → Wait for completion (~30 minutes for 1,000 cases)

3. Download results:
   Each response = structured JSON metadata
```

This one API call replaces 1,000 individual Gemini calls. At 50% the price.

### Phase 3: Online Processing (~2-3 hours per 1,000 cases)

The remaining steps need real-time processing:

```
For each case:
  A. Validate metadata (regex, cross-field)
  B. Chunk text (section-aware, legal boundaries)
  C. Generate contextual prefixes (Flash LLM, 10 concurrent)
  D. Generate embeddings (Gemini, batch of 100)
  E. Generate RAPTOR summaries (online LLM)
  F. Upsert to Pinecone (new first, delete stale)
  G. Build Neo4j citation graph
  H. Update PostgreSQL (chunk_count, ingestion_status)
```

### Phase 4: Quality Check (~2 min)

```
Sample 10 random cases from the batch:
  - Check that all 5 vector types exist in Pinecone
    (chunk, proposition, ratio, headnote, statute)
  - Verify metadata completeness
  - Print extraction confidence distribution

Output:
  "10/10 cases passed quality check"
  "Average confidence: 0.87"
  "Vector coverage: chunk 100%, proposition 95%, ratio 90%"
```

---

## The Cost Math

| Method | Cost per 1,000 cases | Time | Quality |
|--------|---------------------|------|---------|
| Online (one-at-a-time) | ~$68 | ~12 hours | High |
| AI Studio Batch | ~$34 | ~2 hours | LOW (no responseSchema) |
| Vertex AI Batch | **~$34** | **~3 hours** | **High** |

Vertex AI batch gives you the cost savings WITHOUT the quality loss. For 31,000 remaining cases: **$1,054** total.

---

## Resume Capability

The batch script supports `--resume <run_id>`:

```bash
# Start a batch job
python scripts/batch_ingest_vertex.py --year 2024

# If it crashes or you stop it:
python scripts/batch_ingest_vertex.py --resume run_20260328_143052

# It reloads progress.json, skips completed cases, continues from where it left off
```

---

## The Audit Trail

Throughout March 2026, the system went through multiple audits:

### 10x Audit Fix (March 22)
10 major steps addressing all CRITICAL and HIGH findings:
- Step 1: Data flow fixes
- Step 2: Search & ranking fixes
- Step 3: CRAG & evaluation fixes
- Step 4: Prompt & legal reasoning upgrades
- Step 5: Citation & verification fixes
- Step 6: Synthesis & memo quality
- Step 7: Worker & graph improvements
- Step 8: Error handling & resilience
- Step 9: Frontend fixes
- Step 10: Gemini schema compliance

### Silent Failure Audit (March 23)
Found and fixed all places where errors were silently swallowed:
- Every `catch` block now surfaces errors to the UI
- Stream disconnect detection alerts users
- API failures show meaningful messages, not blank screens

### Security Hardening (March 27)
- Removed hardcoded database credentials from scripts
- Added rate limiting, CORS protection
- Indian Kanoon client: circuit breaker (10 failures → stop calling)
- ILIKE injection prevention in search

---

## The Numbers (Production)

| Metric | Value |
|--------|-------|
| Backend tests | 2,185 |
| Frontend tests | 311 |
| API routes | 68 |
| Next.js pages | 25 (built, zero errors) |
| Database migrations | 36 |
| Ingested cases | ~35,000 |
| Statute sections | 2,932 |
| Vector types | 7 |
| Agent nodes | 40+ |
| Interface protocols | 11 |
| Provider implementations | 15 |

---

> **Next: [Chapter 10 — The Road Ahead →](./10-the-road-ahead.md)**
>
> *Where we look at what's coming next — Hindi NLP, more courts, and the vision for Smriti's future.*

---

### In the Code

| What | Where |
|------|-------|
| Original ingestion script | [backend/scripts/ingest_s3.py](../../backend/scripts/ingest_s3.py) |
| Vertex AI batch ingestion | [backend/scripts/batch_ingest_vertex.py](../../backend/scripts/batch_ingest_vertex.py) |
| Batch ingestion design | [docs/plans/2026-03-28-vertex-batch-ingestion-design.md](../plans/2026-03-28-vertex-batch-ingestion-design.md) |
| Batch ingestion plan | [docs/plans/2026-03-28-vertex-batch-ingestion-plan.md](../plans/2026-03-28-vertex-batch-ingestion-plan.md) |
| Pipeline (full) | [backend/app/core/ingestion/pipeline.py](../../backend/app/core/ingestion/pipeline.py) |
| Quality monitoring | [backend/scripts/monitor_ingestion.py](../../backend/scripts/monitor_ingestion.py) |
| 10x audit fix plan | [docs/plans/2026-03-22-research-agent-10x-fix-plan.md](../plans/2026-03-22-research-agent-10x-fix-plan.md) |
| Security audit | [docs/SECURITY_AUDIT.md](../SECURITY_AUDIT.md) |
| Production readiness | [docs/PRODUCTION_READINESS_AUDIT.md](../PRODUCTION_READINESS_AUDIT.md) |
| All migrations | [backend/migrations/versions/](../../backend/migrations/versions/) |
