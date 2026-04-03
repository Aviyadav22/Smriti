# Ingestion State & Execution Plan — Single Source of Truth

**Last updated**: 2026-04-03
**Author**: Automated pipeline audit
**Purpose**: Everything a new agent needs to know to continue ingestion safely.

---

## 1. Current Database State

### PostgreSQL (Supabase — `76.13.185.172:5432/smriti`)
| Metric | Value |
|--------|-------|
| Total cases | **2,861** |
| With ratio_decidendi | 2,828 (98%) |
| Avg extraction_confidence | 0.979 |
| Year range | 1959-2026 |
| case_sections rows | 34,832 |
| case_citation_equivalents | 2,510 |
| case_statute_interpretations | 6,363 |

**Cases by year (top):**
- 2026: 18, 2025: 753, 2024: 751, 2023: 812, 2022: 440
- 2020: 49, 2019: 4, rest: 1-3 each (trial samples)

**Cases by ingestion date:**
- Mar 26: 805 (verified clean — 2024-2026)
- Mar 27: 1,152 (verified clean — 2019-2026, complete metadata only)
- Mar 31: 150 (trial runs, mixed quality)
- Apr 1: 440 (2022-2023 batch)
- Apr 2: 314 (2022 batch)

### Pinecone (Pro plan — $300 free credit, 3-week trial, NO vector limit)
| Metric | Value |
|--------|-------|
| Total vectors | **153,755** |
| Plan | **Pro** (upgraded from Starter) |
| Vector limit | **Unlimited** (Pro plan) |
| Free credit | $300 for 3 weeks |
| Avg vectors/case | ~55 |
| Dimension | 1536 (gemini-embedding-2-preview) |

**723 cases are in PG but have ZERO vectors in Pinecone.**
- File: `backend/trial_reports/missing_vectors.json` (723 case UUIDs)
- All 723 have full_text + metadata + sections in PG — only embedding/upsert failed
- Must be re-embedded before these cases are searchable

### Neo4j (AuraDB Free — 200K node limit)
| Metric | Value |
|--------|-------|
| Case nodes | 11,457 |
| CITES edges | 10,132 |
| Statute nodes | 7,006 |
| Limit | 200K nodes / 400K relationships |

### SQLite Tracker (`backend/data/ingest_tracker.db`)
| Table | Rows |
|-------|------|
| ingestion_progress | 1,958 |
| processed | 1,958 |

---

## 2. What Needs to Be Done

### Task 1: Re-embed 723 cases missing Pinecone vectors
- **Priority**: HIGH (these cases exist in PG but are invisible to search)
- **What**: Read full_text + sections from PG, re-chunk, embed, upsert to Pinecone
- **Cost**: ~$0.50 (embeddings only, no LLM calls needed)
- **Script**: Write a `scripts/backfill_missing_vectors.py` that reads `trial_reports/missing_vectors.json`
- **Risk**: NONE — all 723 have zero vectors (no partial/duplicate risk, verified)

### Task 2: Ingest remaining ~32K cases (1950-2026)
- **Source**: AWS S3 `s3://indian-supreme-court-judgments/` (public, CC-BY-4.0)
- **Already cached locally**: 2022 (1,017 PDFs), 2023 (854 PDFs)
- **Remaining years**: 1950-2021 (~28K cases), plus gaps in 2022-2026 (~4K)
- **Total S3 dataset**: ~35,000 cases
- **Already ingested**: 2,861 (dedup by text_hash)
- **Remaining**: ~32,139 cases

### Task 3: Backfill contextual embeddings (Phase B)
- **Priority**: LOW (after all 35K cases are in PG + basic Pinecone vectors)
- **What**: Generate LLM contextual prefixes for each chunk, re-embed with prefix
- **Script**: `scripts/backfill_contextual_embeddings.py` (already exists)
- **Cost**: ~$3.50/1K cases (50 LLM calls + re-embed)
- **Impact**: ~10-15% retrieval quality improvement for semantic queries

### Task 4: Backfill RAPTOR section summaries (Phase C)
- **Priority**: LOW (after Task 3)
- **What**: Generate section-level summaries, embed, upsert as `vector_type=summary`
- **Script**: Needs new `scripts/backfill_raptor_summaries.py`
- **Cost**: ~$0.50/1K cases (10 LLM calls + embed)
- **Impact**: Section-level search capability

---

## 3. Pipeline Architecture

### Batch Pipeline (`backend/scripts/batch_ingest_vertex.py`)
```
Phase 1: Download S3 tar → Extract PDFs → Parse text (PyMuPDF) → Upload text to GCS
Phase 2: Submit Vertex AI batch job → LLM extracts metadata → Parse JSON results
Phase 3: Chunk → Embed → Upsert to Pinecone → Insert PG → Build Neo4j graph
Phase 4: Quality check (sample 10 cases across all stores)
```

### Turbo Orchestrator (`ingestion/turbo_ingest.py`)
- Spawns 1-4 parallel workers, each with its own GCP account
- Progressive rollout: trial (50) → small (500) → medium (2000) → full
- Quality gates between each step
- Auto-runs `cleanup_metadata.py` after each batch

### Key Scripts
| Script | Purpose |
|--------|---------|
| `backend/scripts/batch_ingest_vertex.py` | Main ingestion pipeline (Phase 1-4) |
| `backend/scripts/ingest_s3.py` | Online (non-batch) ingestion for single years |
| `backend/scripts/cleanup_metadata.py` | Post-ingestion OCR repair + GAN discriminator |
| `backend/scripts/purge_bad_cases.py` | Delete cases from all 3 stores |
| `backend/scripts/resume_phase3.py` | Resume Phase 3 from saved batch results |
| `ingestion/turbo_ingest.py` | Multi-account parallel orchestrator |
| `ingestion/quality_gates.py` | 5-layer quality validation |

---

## 4. Critical Configuration

### ABSOLUTE COST RULE — READ FIRST
**NEVER use AI Studio (API key). ALWAYS use Vertex AI (service account).**
- AI Studio = real money from personal billing
- Vertex AI = FREE $300 trial credits per GCP account
- `GEMINI_USE_VERTEXAI` must ALWAYS be `true`
- If Vertex AI returns 429, reduce concurrency/RPM — NEVER switch to AI Studio
- See `ingestion/COST_RULES.md` for full details

### Environment Variables (set in `ingestion/accounts/env_{a,b,c,d}`)
```bash
# Per-account (MUST differ per worker)
GEMINI_USE_VERTEXAI=true
GEMINI_VERTEXAI_PROJECT=<project-id>
GEMINI_VERTEXAI_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=ingestion/accounts/account_<letter>.json
GCS_BUCKET=smriti-batch-<letter>

# Cost control (MUST be set for ingestion)
GEMINI_THINKING_BUDGET=0           # CRITICAL: disables thinking tokens (~6x cost savings)
SKIP_CONTEXTUAL_EMBEDDINGS=1       # Skip 50 LLM calls/case (backfill later)
SKIP_RAPTOR_SUMMARIES=1            # Skip 10 LLM calls/case (backfill later)

# Storage (same for all workers)
STORAGE_PROVIDER=local             # PDFs saved locally, bulk-upload to GCS later
GCS_PDF_BUCKET=smriti-production-documents  # Future GCS path written to DB now

# Performance tuning (turbo orchestrator sets these automatically)
EMBED_SUB_BATCH=5                  # Texts per embedding sub-batch (default: 5)
EMBED_CONCURRENCY=3                # Parallel embedding calls (default: 3)
EMBED_SLEEP=0.5                    # Sleep between sub-batches in seconds (default: 0.5)
PINECONE_UPSERT_BATCH=300          # Vectors per Pinecone upsert (default: 100)
DATABASE_POOL_SIZE=20              # PG connections per worker (default: 30)
```

### Shared DB Credentials (same across all workers)
```bash
DATABASE_URL=postgresql+asyncpg://smriti:E9tGr2mSXTi1h36LwsmLKbRVooPmlZbYIY5FnYmuzWg=@76.13.185.172:5432/smriti
PINECONE_API_KEY=pcsk_xZ2MX_QLAsifUTrh2vZ9CzND9XdopAijUnx1Pz9EkxDawgwYyinEnCmtBSYF3F5cjbZQp
PINECONE_HOST=https://smriti-legal-y3apxf5.svc.aped-4627-b74a.pinecone.io
NEO4J_URI=neo4j+s://7a4a400f.databases.neo4j.io
NEO4J_USER=7a4a400f
NEO4J_PASSWORD=oEvhe2GWOs7r41pHiuzIOwopN2im3drdOTJsb1R4vqE
```

---

## 5. Cost Model

### With thinking DISABLED + contextual/RAPTOR skipped (Phase A — fast ingest)
| Component | Cost/1K cases | Notes |
|-----------|--------------|-------|
| Batch metadata (gemini-2.5-flash) | ~$15 | 50% batch discount, 1 LLM call/case |
| Chunk embeddings (gemini-embedding-2-preview) | ~$2 | ~50 chunks/case, $0.20/1M tokens |
| Proposition extraction + embed | ~$5 | ~3 LLM calls + embed |
| **Total Phase A** | **~$22/1K** | No contextual, no RAPTOR |

**35K cases Phase A total: ~$770** (fits in 3 accounts × $300 = $900)

### Backfill later (Phase B+C)
| Component | Cost/1K cases |
|-----------|--------------|
| Contextual prefixes (50 LLM calls + re-embed) | ~$3.50 |
| RAPTOR summaries (10 LLM calls + embed) | ~$0.50 |
| **Total Phase B+C** | **~$4/1K** |

**35K cases backfill total: ~$140**

### CRITICAL: Thinking tokens
- `GEMINI_THINKING_BUDGET=0` MUST be set for all ingestion
- Without it: output tokens cost $3.50/1M instead of $0.60/1M (5.8x more)
- A previous $300 account was burned in days due to thinking tokens

---

## 6. Bugs Fixed (Do NOT Reintroduce)

### Data Corruption Bugs (fixed)
| Bug | Fix | File |
|-----|-----|------|
| Batch `custom_id` mapping — responses mismatched to wrong cases | Added `custom_id` per request, halt if >10% missing | `batch_ingest_vertex.py` |
| Cross-contamination — LLM hallucination on OCR-degraded PDFs | Prompt grounding + confidence gating + field stripping | `metadata.py`, `prompts.py` |
| PDF boundary overlap (pre-1964) | Boundary stripping via header pattern detection | `pdf.py` |
| "More judges wins" merge — hallucinated judges override correct | Judge text validation + tenure check before merge | `metadata.py` |
| RAPTOR vectors deleted by stale cleanup | Track summary vector IDs in `new_vector_ids` | `pipeline.py` |
| Partial embed_batch corrupts alignment | Per-batch count validation before `extend()` | `pipeline.py` |
| `asyncio.Event()` before event loop | `_init_shutdown_event()` inside `run_pipeline()` | `batch_ingest_vertex.py` |
| Progress file corruption on crash | Atomic write via tmp + `os.replace()` | `batch_ingest_vertex.py` |
| FTS trigger ALTER TABLE crashes Windows process | Disabled (no-op) | `ingest_s3.py` |
| GCS PDF upload causes OOM on large batches | Removed per-PDF GCS upload from Phase 1 | `batch_ingest_vertex.py` |
| Oversized PDFs (>250 pages) crash process | Skip with warning | `batch_ingest_vertex.py` |

### Quality Fixes (active)
| Fix | What | File |
|-----|------|------|
| OCR act name repair | Space-breaks, letter corruption, digit corruption | `extractor.py` |
| GAN discriminator for cases_cited | Separates named citations from bare refs | `extractor.py` |
| Acts_cited discriminator | 50+ regex rules reject garbage entries | `extractor.py` |
| Case type vs case number validation | Corrects civil/criminal mismatch | `metadata.py` |
| Embedding dimension validation | Checks `len(embedding) == 1536` before upsert | `pipeline.py` |

### Speed Fixes
| Fix | Before | After |
|-----|--------|-------|
| Thinking tokens disabled | $3.50/1M output | $0.60/1M output (6x savings) |
| EMBED_SLEEP reduced | 2-3s per sub-batch | 0.5s (4-6x faster embedding) |
| EMBED_SUB_BATCH increased | 3 | 5 |
| EMBED_CONCURRENCY increased | 1-2 | 3 |
| SKIP_CONTEXTUAL_EMBEDDINGS flag | 50 LLM calls/case | 0 (backfill later) |
| SKIP_RAPTOR_SUMMARIES flag | 10 LLM calls/case | 0 (backfill later) |
| Global limit in turbo worker | limit × years (10x overspend) | Exact global limit |

---

## 7. Pinecone Vector Budget (Pro plan — unlimited)

Pinecone upgraded to Pro ($300 free credit, 3 weeks). No vector limit.

At 35K cases, ~30 vectors/case average:
| Vector Type | Est. Count | Include? |
|-------------|-----------|----------|
| chunk | ~700K | YES — core search |
| proposition | ~105K | YES — legal principle search |
| ratio | ~35K | YES — ratio decidendi |
| headnote | ~35K | YES — structured holdings |
| summary (RAPTOR) | ~70K | SKIP Phase A, backfill Phase C |
| statute | ~30K | YES — from statute ingestion |
| community | ~30K | SKIP Phase A, backfill later |
| **Total** | **~1.005M** | No limit on Pro |

**No need to skip vectors for space.** RAPTOR and community are skipped only for
SPEED (saves 60 LLM calls/case), not for space. Backfill adds them later.

---

## 8. Known Limitations / Accepted Risks

1. **SKIP LOCKED dedup**: If 2 workers process the same text_hash concurrently, Worker B wastes API credits (PG dedup catches it at insert). Rare with year-based splitting.

2. **Neo4j dual merge keys**: Main nodes use `{id: uuid}`, cited-case placeholders use `{citation: "..."}`. When a cited case is later ingested, it creates a second node. Needs periodic dedup.

3. **Contextual embeddings skipped**: Phase A chunk vectors are "plain" (no contextual prefix). Search works but quality is ~10-15% lower for semantic queries. Backfill in Phase B re-embeds with prefixes (overwrites by same vector ID).

4. **RAPTOR summaries skipped**: Section-level search not available until Phase C backfill.

5. **PDFs not in GCS**: `pdf_storage_path` in DB points to future `gs://smriti-production-documents/cases/{id}/{name}.pdf` but actual upload happens later. PDF viewer will 404 until bulk upload.

6. **Free trial Vertex AI quotas are LOW**: New GCP accounts may hit 429 rate limits with concurrency >1. Use `--concurrency 1 --rpm-limit 15` for new accounts, or request quota increase.

---

## 9. Execution Checklist

### Before Starting
- [ ] Verify all 4 GCP accounts have Vertex AI API enabled
- [ ] Verify all 4 have service account JSONs in `ingestion/accounts/`
- [ ] Verify all 4 have GCS buckets created (`smriti-batch-{a,b,c,d}`)
- [ ] Verify `GEMINI_THINKING_BUDGET=0` is set in all env files
- [ ] Run `python ingestion/turbo_ingest.py --setup` to validate connectivity
- [ ] Check Pinecone vector count (must be <850K to start)

### Step 1: Re-embed 723 missing cases
```bash
# Write and run backfill script for missing vectors
python scripts/backfill_missing_vectors.py --input trial_reports/missing_vectors.json
```

### Step 2: Trial run (50 cases)
```bash
python ingestion/turbo_ingest.py --trial --account a --limit 50
# Verify: PG metadata correct, Pinecone vectors present, Neo4j nodes created
# Check GCP billing console: should be ~$1-2 for 50 cases
```

### Step 3: Progressive rollout
```bash
python ingestion/turbo_ingest.py --run --step small   # 500/account = 2,000 total
# Validate quality, check costs
python ingestion/turbo_ingest.py --run --step medium  # 2,000/account = 8,000 total
# Validate quality, check costs
python ingestion/turbo_ingest.py --run --step full    # Remaining (~6,000/account)
# Final validation
```

### Step 4: Post-ingestion cleanup
```bash
python scripts/cleanup_metadata.py --since 2026-04-03   # OCR repair + GAN discriminator
python ingestion/turbo_ingest.py --quality-check         # Cross-store integrity
python ingestion/turbo_ingest.py --retry-failed          # Re-process any failures
```

### Step 5: Backfill (Phase B+C, after all 35K searchable)
```bash
# Phase B: Contextual embeddings
python scripts/backfill_contextual_embeddings.py --all
# Phase C: RAPTOR summaries
python scripts/backfill_raptor_summaries.py --all
```

---

## 10. File Map

```
d:/Startup/Smriti/
  ingestion/
    INGESTION_STATE.md              # THIS FILE — single source of truth
    TURBO_INGESTION_DESIGN.md       # Architecture & design decisions
    turbo_ingest.py                 # Multi-account orchestrator
    quality_gates.py                # 5-layer quality validation
    accounts/
      account_{a,b,c,d}.json        # GCP service account keys (gitignored)
      env_{a,b,c,d}                 # Per-account environment variables
      env_template                  # Template for new accounts
    logs/                           # Per-worker log files
    runs/                           # Run artifacts (configs, quality reports)

  backend/
    scripts/
      batch_ingest_vertex.py        # Main pipeline (Phase 1-4)
      ingest_s3.py                  # Online ingestion (single year)
      cleanup_metadata.py           # Post-ingestion quality fixes
      purge_bad_cases.py            # Delete cases from all stores
      resume_phase3.py              # Resume Phase 3 from saved results
      backfill_contextual_embeddings.py  # Phase B backfill
      backfill_missing_vectors.py   # Re-embed cases missing vectors (TODO: create)
    app/core/ingestion/
      pipeline.py                   # Core ingestion logic
      metadata.py                   # Metadata validation + merge
      pdf.py                        # PDF text extraction + boundary stripping
      contextual_embeddings.py      # LLM contextual prefix generation
      section_summarizer.py         # RAPTOR section summaries
    app/core/legal/
      extractor.py                  # Citation/act extraction + GAN discriminator
      prompts.py                    # All LLM prompts
    app/core/providers/
      llm/gemini.py                 # Gemini LLM (thinking budget control here)
      embeddings/gemini.py          # Gemini embeddings (sleep/batch config here)
    trial_reports/
      missing_vectors.json          # 723 case UUIDs needing re-embedding
      keep_ids.json                 # 1,991 verified clean case UUIDs
```
