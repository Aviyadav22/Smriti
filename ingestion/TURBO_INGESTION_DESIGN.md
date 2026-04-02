# Turbo Ingestion Pipeline — Design & Execution Guide

**Date**: 2026-04-02
**Goal**: Ingest 35K Indian Supreme Court judgments in ~3-4 days (Phase 1), then 100K (Phase 2)
**Current rate**: ~300 cases/day. **Target**: ~10,000 cases/day.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Constraints & Budget](#2-constraints--budget)
3. [Infrastructure](#3-infrastructure)
4. [Account Setup](#4-account-setup)
5. [Pipeline Phases](#5-pipeline-phases)
6. [Quality Defense System](#6-quality-defense-system)
7. [Orchestrator Design](#7-orchestrator-design)
8. [Performance Tuning](#8-performance-tuning)
9. [Failure Recovery](#9-failure-recovery)
10. [Monitoring](#10-monitoring)
11. [Execution Playbook](#11-execution-playbook)
12. [Risk Register](#12-risk-register)

---

## 1. Architecture Overview

```
                    LOCAL MACHINE (16GB RAM, Ryzen 9)
                    ================================
                    
    [Orchestrator] ─── spawns 4 Python processes in parallel
         │
         ├── Worker 1 (Account A) ──┐
         ├── Worker 2 (Account B) ──┤
         ├── Worker 3 (Account C) ──┤── Each runs batch_ingest_vertex.py
         └── Worker 4 (Account D) ──┘   with its own GCP credentials
                                        and ~8,750 cases
         │
         └── All workers write to shared databases:
              ├── PostgreSQL (Hostinger VM, 8GB RAM)
              ├── Pinecone Starter (1M vectors)
              └── Neo4j AuraDB Free (200K nodes)
```

**Key principle**: Each GCP account has its own Vertex AI quotas and $300 credits.
By running 4 workers in parallel, we get 4x throughput on the LLM/embedding layer
while sharing the downstream databases.

**No Docker**. Run Python directly on local machine — full 16GB RAM available.

---

## 2. Constraints & Budget

### Credits
| Account | Credits | Allocated Cases | Est. Cost |
|---------|---------|----------------|-----------|
| A       | $300    | ~8,750         | ~$298     |
| B       | $300    | ~8,750         | ~$298     |
| C       | $300    | ~8,750         | ~$298     |
| D       | $300    | ~8,750         | ~$298     |
| **Total** | **$1,200** | **35,000** | **~$1,190** |

### Cost Breakdown Per 1,000 Cases (~$34)

**CRITICAL**: All costs assume `GEMINI_THINKING_BUDGET=0` (thinking DISABLED).
With thinking enabled (default), output tokens cost $3.50/1M instead of $0.60/1M,
making costs ~6x higher (~$200/1K cases instead of ~$34).

| Component | Cost/1K | Notes |
|-----------|---------|-------|
| Batch metadata (Flash, no thinking) | ~$15 | 50% batch discount, thinking disabled in JSONL |
| Contextual prefixes (Flash online, no thinking) | ~$12 | `GEMINI_THINKING_BUDGET=0` in env |
| RAPTOR summaries (Flash online, no thinking) | ~$5 | Section summaries |
| Embeddings (embedding-2-preview) | ~$2 | $0.20/1M tokens |
| **Total** | **~$34** | **Only with thinking disabled** |

The turbo orchestrator sets `GEMINI_THINKING_BUDGET=0` automatically for all workers.

### Hard Limits
| Resource | Limit | 35K Impact | Action |
|----------|-------|-----------|--------|
| Pinecone Starter | 1M vectors | ~1.05M (tight!) | Skip community vectors, monitor count |
| Neo4j AuraDB Free | 200K nodes / 400K rels | ~70K nodes, ~150K rels | Safe |
| PostgreSQL (Hostinger) | 8GB RAM | Fine for concurrent writes | Monitor connections |
| Vertex AI batch jobs | 75 per region per project | Only need 1-2 per account | No issue |

### Pinecone Vector Budget
At 35K cases, ~30 vectors/case average:
| Vector Type | Count Estimate | Priority | Include? |
|-------------|---------------|----------|----------|
| chunk | ~700K | MUST | Yes |
| proposition | ~105K | HIGH | Yes |
| ratio | ~35K | HIGH | Yes |
| headnote | ~35K | HIGH | Yes |
| summary (RAPTOR) | ~70K | MEDIUM | Yes |
| statute | ~30K | MEDIUM | Yes |
| community | ~30K | LOW | **SKIP** (saves ~30K vectors) |
| **Total** | **~975K** | | Under 1M |

**Decision**: Skip community vectors to stay under 1M. Can generate later after upgrading Pinecone.

---

## 3. Infrastructure

### Local Machine (Primary)
- **CPU**: Ryzen 9 (plenty for I/O-bound work)
- **RAM**: 16GB (no Docker overhead)
- **GPU**: RTX 3060 (unused — ingestion is API-bound, not compute)
- **Network**: 50+ Mbps
- **OS**: Windows 11, using bash shell
- **Python**: 3.12, run scripts directly (no Docker)

### Database Targets
| Service | Host | Connection Limit | Notes |
|---------|------|-----------------|-------|
| PostgreSQL | Hostinger VM (8GB) | ~100 connections | Pool size 30 per worker = 120 total. May need to tune `max_connections` |
| Pinecone | Cloud (Starter) | Unlimited API calls | Upsert batch 100 vectors/call |
| Neo4j AuraDB | Cloud (Free) | 50 connections | Batch 500 nodes/op |

**PostgreSQL tuning needed**: Default `max_connections` on Hostinger is likely 100. With 4 workers each using pool_size=30, we need 120. Either:
- Reduce pool_size to 20 per worker (80 total), OR
- Increase `max_connections` to 150 on Hostinger VM

---

## 4. Account Setup

### Create 4 GCP Accounts
1. Create 4 Gmail accounts (or use existing ones)
2. For each: Sign up for GCP → get $300 free trial credits (90 days)
3. Enable Vertex AI API on each project
4. Create a service account in each project with "Vertex AI User" + "Storage Admin" roles
5. Download the service account JSON key for each
6. Create a GCS bucket in each project: `smriti-batch-ingestion-{N}`

### Credential Files
Place service account JSONs in `ingestion/accounts/`:
```
ingestion/accounts/
  account_a.json    # GCP project 1
  account_b.json    # GCP project 2
  account_c.json    # GCP project 3
  account_d.json    # GCP project 4
```

### .env Per Account
Each worker needs its own environment. Create `ingestion/accounts/env_{a,b,c,d}`:
```bash
# ingestion/accounts/env_a
GEMINI_USE_VERTEXAI=true
GEMINI_VERTEXAI_PROJECT=<project-id-from-gcp-account-1>
GEMINI_VERTEXAI_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=ingestion/accounts/account_a.json
GCS_BUCKET=smriti-batch-a
STORAGE_PROVIDER=local
GCS_PDF_BUCKET=smriti-production-documents

# Shared DB credentials (same across all workers — copy from backend/.env)
DATABASE_URL=<copy from backend/.env>
PINECONE_API_KEY=<copy from backend/.env>
PINECONE_HOST=<copy from backend/.env>
NEO4J_URI=<copy from backend/.env>
NEO4J_USER=<copy from backend/.env>
NEO4J_PASSWORD=<copy from backend/.env>
```

**Notes:**
- `GCS_BUCKET`: Per-account bucket for Phase 2 batch JSONL only (~10 MB). Create one per account.
- `STORAGE_PROVIDER=local`: PDFs saved locally during ingestion, bulk-uploaded to GCS later.
- `GCS_PDF_BUCKET`: The FINAL production GCS bucket name. Written into `pdf_storage_path` in DB
  so retrieval references the correct `gs://` path even before actual upload.
- All 4 env files share the SAME DB credentials (PostgreSQL, Pinecone, Neo4j).

### GCS Setup Per Account (Minimal)
Each account only needs ONE small bucket for batch JSONL:
1. Cloud Storage → Create Bucket → Name: `smriti-batch-{a/b/c/d}` → Region: us-central1
2. No PDF upload — PDFs are bulk-uploaded to a single production bucket later.

---

## 5. Pipeline Phases

### Phase 1: Text Extraction + GCS Upload (No API cost)
- Downloads S3 data (public, free), extracts PDFs, parses text via pdfplumber
- Uploads PDFs to GCS for batch API
- **Run once** — output is shared across all 4 workers
- **Duration**: ~10 hours for 35K cases
- **Optimization**: Run with `--limit 35000 --all` to extract everything in one pass

**Split strategy after Phase 1**:
The orchestrator splits the manifest into 4 equal chunks and assigns each to an account.
Each chunk gets its own run directory: `ingestion/runs/turbo_{account}_{date}/`

### Phase 2: Batch Metadata Extraction (50% discount)
- Each worker submits its ~8,750 cases as a Vertex AI batch job
- 4 batch jobs run in parallel across 4 GCP projects
- **Typical wait**: 2-12 hours (off-peak is faster)
- **Cost**: ~$15/1K cases × 8.75K = ~$131 per account
- **Quality gate**: >10% parse failures → HALT that worker

**GCS bucket per account**: Each account's batch job uses its own GCS bucket to avoid
cross-project permission issues.

### Phase 3: Online Processing (Embedding + Storage)
- Chunk text, contextualize, embed, upsert to Pinecone, build Neo4j graph
- **4 workers run in parallel**, each processing its assigned ~8,750 cases
- **Concurrency per worker**: 8 cases simultaneously
- **RPM per worker**: 150 (well within Vertex AI quotas)
- **Duration**: ~19 hours (all 4 workers finish around the same time)

### Phase 4: Quality Check
- Each worker auto-runs quality check on its batch
- Samples 10 cases, verifies PG + Pinecone + Neo4j
- Final cross-worker validation by orchestrator

---

## 6. Quality Defense System

### Layer 1: Trial Run (Before Committing Credits)

Run 50 cases through the FULL pipeline on Account A:
```bash
python ingestion/turbo_ingest.py --trial --account a --limit 50
```

**Automated checks after trial**:
- All 50 cases have metadata in PostgreSQL
- All 50 have >0 vectors in Pinecone with correct case_id
- At least 40/50 have Neo4j citation edges
- Metadata fields are non-empty: title, citation, court, year, judge
- No two cases share the same metadata (the 4K batch corruption bug)
- Embedding dimensions = 1536 for all vectors
- Chunk count is between 5-500 for each case

**Manual spot check**: Open 10 random cases, verify metadata makes sense.
**If trial fails**: Fix the issue, re-run trial. Do NOT proceed to full run.

### Layer 2: Progressive Rollout

Each account follows this schedule:
```
Trial:  50 cases   → validate → ~$1.70 spent
Small:  500 cases  → validate → ~$17 spent  (cumulative: ~$19)
Medium: 2,000 cases → validate → ~$68 spent  (cumulative: ~$87)
Full:   6,200 cases → validate → ~$211 spent (cumulative: ~$298)
```

**Gate between each step**: Automated quality check must PASS before proceeding.
At no point do we risk more than $68 without having validated on 550+ real cases.

### Layer 3: Automated Quality Gates Between Phases

**After Phase 2 (batch metadata), before Phase 3 (expensive embeddings)**:

```python
def quality_gate_phase2(metadata_results: dict) -> bool:
    """Validate batch metadata before spending on embeddings."""
    checks = {
        "total_results": len(metadata_results),
        "has_title": sum(1 for m in metadata_results.values() if m.get("title")),
        "has_citation": sum(1 for m in metadata_results.values() if m.get("citation")),
        "has_year": sum(1 for m in metadata_results.values() if m.get("year")),
        "has_judge": sum(1 for m in metadata_results.values() if m.get("judge")),
        "unique_titles": len(set(m.get("title", "") for m in metadata_results.values())),
    }
    
    total = checks["total_results"]
    # At least 90% have core fields
    assert checks["has_title"] >= total * 0.9, f"Only {checks['has_title']}/{total} have title"
    assert checks["has_year"] >= total * 0.9, f"Only {checks['has_year']}/{total} have year"
    # Titles are unique (catches the cross-contamination bug)
    assert checks["unique_titles"] >= total * 0.85, f"Only {checks['unique_titles']} unique titles"
    return True
```

### Layer 4: Per-Case Validation During Phase 3

Before upserting vectors for each case:
- `chunk_count` is between 5 and 500 (not 0, not 5000)
- All embeddings have exactly 1536 dimensions
- `case_id` in Pinecone metadata matches the current case
- `text_hash` is unique (dedup check)
- If metadata fields look identical to previous case → HALT and flag

On failure: **skip the case, log it, continue**. Don't abort the whole run.
Failed cases saved to `ingestion/runs/{run_id}/failed_cases.json` for retry.

### Layer 5: Post-Batch Spot Check

After each rollout step completes:
```python
def post_batch_spot_check(case_ids: list[str], sample_size: int = 10) -> dict:
    """Query all databases to verify data integrity."""
    sample = random.sample(case_ids, min(sample_size, len(case_ids)))
    results = {}
    for case_id in sample:
        results[case_id] = {
            "pg_exists": check_postgres(case_id),       # Has metadata row
            "pg_chunk_count": get_chunk_count(case_id),  # >0 chunks
            "pinecone_vectors": count_pinecone_vectors(case_id),  # >0
            "neo4j_node": check_neo4j_node(case_id),     # Has case node
            "neo4j_citations": count_neo4j_citations(case_id),  # >=0
            "metadata_valid": validate_metadata_fields(case_id),
        }
    return results
```

---

## 7. Orchestrator Design

The orchestrator (`ingestion/turbo_ingest.py`) manages the entire process:

```
turbo_ingest.py
  ├── --setup          # Validate accounts, test credentials
  ├── --trial          # Run 50-case trial on one account
  ├── --run            # Full progressive rollout across all accounts
  ├── --resume         # Resume from last checkpoint
  ├── --status         # Show progress across all workers
  ├── --quality-check  # Run quality checks on completed runs
  └── --account {a,b,c,d}  # Target specific account
```

### Orchestrator Flow

```
1. --setup
   ├── Validate all 4 account credentials (test Vertex AI API call)
   ├── Verify PostgreSQL connectivity and max_connections
   ├── Verify Pinecone connectivity and current vector count
   ├── Verify Neo4j connectivity and current node count
   └── Print budget summary

2. --trial (Account A only)
   ├── Phase 1: Extract 50 cases
   ├── Phase 2: Batch metadata (50 cases)
   ├── Phase 3: Online processing (50 cases)
   ├── Layer 1 quality checks (automated)
   ├── Print results for manual review
   └── Ask: "Trial passed. Proceed to small batch? [y/n]"

3. --run (All 4 accounts, progressive)
   ├── Phase 1: Extract ALL 35K cases (once, shared)
   ├── Split manifest into 4 chunks
   ├── For each rollout step (500 → 2000 → remaining):
   │   ├── Launch 4 workers in parallel (subprocess per account)
   │   ├── Each worker: Phase 2 → quality gate → Phase 3
   │   ├── Wait for all workers to complete
   │   ├── Run Layer 5 spot check
   │   └── Print results, ask to continue
   └── Final quality report
```

### Worker Process Isolation

Each worker runs as a **separate Python subprocess** with:
- Its own `GOOGLE_APPLICATION_CREDENTIALS` env var
- Its own rate limiters (no shared state)
- Its own GCS bucket for batch jobs
- Shared database connections (PostgreSQL, Pinecone, Neo4j)

```python
# Orchestrator spawns workers like:
subprocess.Popen([
    sys.executable, "backend/scripts/batch_ingest_vertex.py",
    "--year-range", "1950-1970",  # Each worker gets a year range
    "--rpm-limit", "150",
    "--concurrency", "8",
    "--limit", "500",  # Progressive limit
], env={
    **os.environ,
    "GOOGLE_APPLICATION_CREDENTIALS": f"ingestion/accounts/account_{acc}.json",
    "GEMINI_VERTEXAI_PROJECT": f"smriti-ingest-{acc}",
    "GCS_BUCKET": f"smriti-batch-ingestion-{acc}",
    "WORKER_ID": acc,
})
```

---

## 8. Performance Tuning

### Current vs Turbo Settings

| Parameter | Current | Turbo (per worker) | Total (4 workers) |
|-----------|---------|-------------------|-------------------|
| Concurrency | 1 | 8 | 32 |
| LLM RPM | 30 | 150 | 600 |
| Embed RPM | 60 | 300 | 1,200 |
| Embed semaphore | 2 | 8 | 32 |
| Embed sub-batch | 3 | 20 | 80 |
| Embed sleep | 2.0s | 0.3s | - |
| Pinecone batch | 100 | 300 | - |
| DB pool size | 30 | 20 | 80 |

### Code Changes Required

**1. Embedding concurrency** (`backend/app/core/providers/embeddings/gemini.py`):
```python
# Current (line 190-191):
_SUB_BATCH = 3
sem = asyncio.Semaphore(2)

# Turbo:
_SUB_BATCH = 20
sem = asyncio.Semaphore(8)

# Current (line 203):
await asyncio.sleep(2.0)

# Turbo:
await asyncio.sleep(0.3)
```

Make these configurable via environment variables instead of hardcoded:
```python
_SUB_BATCH = int(os.environ.get("EMBED_SUB_BATCH", "3"))
_EMBED_CONCURRENCY = int(os.environ.get("EMBED_CONCURRENCY", "2"))
_EMBED_SLEEP = float(os.environ.get("EMBED_SLEEP", "2.0"))
```

**2. DB pool size** (`backend/app/core/config.py`):
```python
# Reduce from 30 to 20 for multi-worker safety
database_pool_size: int = int(os.environ.get("DATABASE_POOL_SIZE", "20"))
```

**3. Pinecone upsert batch** (`backend/app/core/ingestion/pipeline.py`):
```python
# Current (line 1098): hardcoded 100
# Make configurable:
_UPSERT_BATCH = int(os.environ.get("PINECONE_UPSERT_BATCH", "100"))
```

**4. Skip community vectors** (`backend/app/core/ingestion/pipeline.py`):
Add env flag: `SKIP_COMMUNITY_VECTORS=true`

**5. Garbage collection** (add to `batch_ingest_vertex.py` Phase 3):
```python
import gc
# After each case completes:
if processed_count % 50 == 0:
    gc.collect()
```

---

## 9. Failure Recovery

### Credits Exhausted Mid-Run
The existing pipeline already detects 403/billing errors and saves progress:
```python
except (PermissionError, gapi_exceptions.Forbidden) as perm_exc:
    credits_exhausted = True
    # Saves progress.json with completed cases
```

**Recovery**: Switch to a different account's credentials and `--resume`.

### Network Failure
- All providers use tenacity retry (5 attempts, exponential backoff 2-60s)
- Progress saved after every case
- `--resume` picks up from last completed case

### Phase 2 Batch Job Failure
- Batch job name saved to `batch_job_name.txt`
- Can poll manually: `client.batches.get(name=job_name)`
- If batch fails: re-submit just the failed account's chunk

### Database Connection Issues
- PostgreSQL: asyncpg pool with 20 connections, 30s timeout, auto-reconnect
- Pinecone: HTTP client with retry, no persistent connections
- Neo4j: Connection pool with auto-renewal

### Partial Ingestion (Some Cases Failed)
- Failed cases logged to `failed_cases.json` per run
- After all workers complete, collect failed cases across all runs
- Re-run failed cases with `--resume` on whichever account has remaining credits

---

## 10. Monitoring

### Real-Time Progress
Each worker logs to its own file:
```
ingestion/logs/worker_a.log
ingestion/logs/worker_b.log
ingestion/logs/worker_c.log
ingestion/logs/worker_d.log
```

The orchestrator provides a dashboard:
```bash
python ingestion/turbo_ingest.py --status
```
Output:
```
Worker A: Phase 3 - 4,521/8,750 (51.7%) | 127 failed | ~$156 spent
Worker B: Phase 3 - 3,892/8,750 (44.5%) | 89 failed  | ~$134 spent
Worker C: Phase 2 - Batch job RUNNING (submitted 2h ago)
Worker D: Phase 3 - 5,102/8,750 (58.3%) | 201 failed | ~$176 spent
─────────────────────────────────────────────────────
Total: 13,515/35,000 (38.6%) | Pinecone: 412K/1M vectors | Neo4j: 28K nodes
```

### Key Metrics to Watch
1. **Credits remaining** per account (check GCP billing console)
2. **Pinecone vector count** (approaching 1M limit)
3. **PostgreSQL connection count** (`SELECT count(*) FROM pg_stat_activity`)
4. **Neo4j node count** (approaching 200K limit)
5. **Failure rate** per worker (should be <5%)
6. **RAM usage** on local machine (`htop` or Task Manager)

---

## 11. Execution Playbook

### Day 0: Setup (~2 hours)

```bash
# 1. Create ingestion virtual environment (separate from backend)
cd d:/Startup/Smriti
python -m venv ingestion/.venv
source ingestion/.venv/Scripts/activate  # Windows bash
pip install -r backend/requirements.txt

# 2. Place account credentials
# Copy 4 service account JSONs to ingestion/accounts/

# 3. Create env files for each account
# Edit ingestion/accounts/env_a through env_d

# 4. Validate setup
python ingestion/turbo_ingest.py --setup
```

### Day 0: Trial Run (~4-6 hours)

```bash
# Run 50-case trial on Account A
python ingestion/turbo_ingest.py --trial --account a --limit 50

# Review output:
# - Check ingestion/runs/trial_a/quality_report.json
# - Manually inspect 10 cases in PostgreSQL
# - Verify Pinecone vectors via console
# - Check Neo4j browser for citation graph

# If trial passes → proceed
```

### Day 1: Progressive Rollout — Small Batch (~8-12 hours)

```bash
# Phase 1: Extract all 35K cases (one-time, ~10 hours)
python ingestion/turbo_ingest.py --extract-all

# Small batch: 500 cases per account (2,000 total)
python ingestion/turbo_ingest.py --run --step small
# This submits 4 batch jobs, waits for completion, runs Phase 3, validates
```

### Day 1-2: Progressive Rollout — Medium Batch (~12-18 hours)

```bash
# Medium: 2,000 cases per account (8,000 total)
python ingestion/turbo_ingest.py --run --step medium
```

### Day 2-3: Full Batch (~24-36 hours)

```bash
# Remaining: ~6,200 cases per account (~24,800 total)
python ingestion/turbo_ingest.py --run --step full
```

### Day 3-4: Cleanup & Validation

```bash
# Run comprehensive quality check
python ingestion/turbo_ingest.py --quality-check

# Retry failed cases
python ingestion/turbo_ingest.py --retry-failed

# Rebuild FTS vectors (if not done per-worker)
python backend/scripts/batch_ingest_vertex.py --rebuild-fts

# Final statistics
python ingestion/turbo_ingest.py --status --final
```

---

## 12. Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| Metadata cross-contamination (4K bug repeat) | HIGH | LOW (fixed) | Layer 3 uniqueness check, trial run |
| Pinecone hits 1M vector limit | HIGH | MEDIUM | Skip community vectors, monitor count |
| Neo4j hits 200K node limit | MEDIUM | LOW | ~70K nodes expected, well under limit |
| Credits exhausted early (cost > $34/1K) | HIGH | LOW | Progressive rollout limits blast radius |
| PostgreSQL max_connections exceeded | MEDIUM | MEDIUM | Reduce pool_size to 20/worker |
| Batch job takes >48 hours | LOW | LOW | Can cancel and re-submit to different region |
| RAM exhaustion on local machine | LOW | LOW | No Docker, 16GB available, GC every 50 cases |
| Network interruption | LOW | MEDIUM | Resume from progress.json, tenacity retries |
| Rate limiting (429 errors) | LOW | MEDIUM | 150 RPM is conservative, exponential backoff |
| Hostinger VM goes down | HIGH | LOW | Resume after VM recovery, data in progress.json |

---

## File Structure

```
ingestion/
  TURBO_INGESTION_DESIGN.md    # This file — single source of truth
  turbo_ingest.py              # Orchestrator script
  quality_gates.py             # Quality validation functions
  accounts/
    account_a.json             # GCP service account key (gitignored)
    account_b.json
    account_c.json
    account_d.json
    env_a                      # Per-account environment variables
    env_b
    env_c
    env_d
  logs/
    worker_a.log               # Per-worker log files
    worker_b.log
    worker_c.log
    worker_d.log
  runs/
    trial_a/                   # Trial run artifacts
    turbo_small_YYYYMMDD/      # Small batch run
    turbo_medium_YYYYMMDD/     # Medium batch run
    turbo_full_YYYYMMDD/       # Full batch run
```

The existing pipeline code stays in `backend/` — this folder only contains
the orchestrator, quality gates, and run artifacts. The orchestrator calls
`backend/scripts/batch_ingest_vertex.py` as a subprocess with the right
environment variables per account.
