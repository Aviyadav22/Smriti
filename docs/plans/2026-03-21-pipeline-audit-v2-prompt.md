# Implementation Loop Prompt — Pipeline Audit V2 Fixes

Copy everything below the `---` line and paste it into a new Claude Code terminal.

---

You are implementing the Pipeline Audit V2 fixes for the Smriti ingestion pipeline. This is a critical hardening pass to make the pipeline reliable for 35K Supreme Court case ingestion.

## Your Loop

You will operate in a strict implementation loop:

1. **Read the checklist**: `docs/plans/2026-03-21-pipeline-audit-v2-checklist.md`
2. **Find the first unchecked item** (line starts with `- [ ]`)
3. **Read the plan**: `docs/plans/2026-03-21-pipeline-audit-v2-fixes.md` — find the corresponding step for full context, E2E impact notes, and exact code guidance
4. **Read the target file(s)** before making any changes — line numbers may have shifted from prior steps
5. **Implement the step** — follow the plan's code guidance exactly, but adapt to actual line numbers you see
6. **If the step is a test-run step**, run `cd backend && python -m pytest tests/unit/ -x -q` and fix any failures before proceeding
7. **Update the checklist** — change `- [ ]` to `- [x]` for the completed step
8. **Repeat from step 1**

## Critical Rules

- **One step at a time**. Never implement two steps in a single pass.
- **Read before writing**. Always read the target file before editing. Line numbers in the plan are approximate — find the actual code.
- **Tests must pass** after each test-run step (2.3, 3.5, 4.4, 5.4, 6.3, 7.2). Do not proceed until green.
- **Follow the plan's code** as closely as possible, but adapt to what you actually see in the file.
- **Check E2E notes** in the plan for each step — they describe cross-file impacts you must account for.
- **Don't over-engineer** — implement exactly what the plan says, nothing more.
- **Migration chain**: 028 → 029 → 030 → 031. Each new migration's `down_revision` must point to the previous one.
- **Update the checklist immediately** after each step — this is your progress tracker.

## Context

- **Project**: Smriti — AI-powered Indian legal research platform
- **Tech stack**: FastAPI, PostgreSQL 16, Pinecone, Neo4j AuraDB, Gemini 2.5 Pro/Flash
- **Backend**: `backend/` directory, Python 3.12+
- **Tests**: pytest, `backend/tests/unit/` for unit tests
- **Migrations**: Alembic, `backend/migrations/versions/`
- **Current migration head**: 029

## Files You'll Touch

| Phase | Files |
|-------|-------|
| 1 | `backend/migrations/versions/028_coram_size.py` |
| 2 | NEW `backend/migrations/versions/030_fts_trigger_optimization.py`, `backend/app/core/ingestion/pipeline.py` |
| 3 | `backend/scripts/ingest_s3.py` |
| 4 | `backend/app/core/providers/storage/gcs_storage.py`, `backend/app/core/providers/graph/neo4j_store.py` |
| 5 | `backend/scripts/ingest_s3.py`, `backend/app/core/ingestion/pdf.py`, `backend/app/core/ingestion/pipeline.py`, `backend/app/core/ingestion/chunker.py` |
| 6 | NEW `backend/migrations/versions/031_text_hash_unique_index.py`, `backend/app/core/ingestion/pipeline.py` |
| 7 | `backend/app/models/case.py` |

## Key Design Decisions

1. **OCR page limit is 500** (not 50). Many SC judgments are 100-300 pages. Constitutional bench cases (Kesavananda, Ayodhya) can be 500-1000+. The 500-page limit handles 99%+ of real cases.

2. **Truncated cases are tracked, not lost**. Step 5.2a adds a `warnings` column to IngestTracker. Step 5.2b caps OCR at 500 pages but **still ingests partial text** (doesn't return empty). Step 5.2c wires truncation info back to the tracker. After the full 35K run, query:
   ```sql
   SELECT doc_key, warnings FROM ingestion_progress WHERE warnings IS NOT NULL;
   ```
   This gives the exact list of cases to re-ingest individually with higher limits or manual OCR.

3. **party_counsel uses `"name"` key** (matching LLM schema and validation), NOT `"counsel_name"`. The pipeline.py graph builder is the one that's wrong.

4. **FTS trigger gets UPDATE OF clause** — only fires on FTS-relevant column changes. After this, `updated_at` is no longer auto-set by the trigger, so all raw SQL on `cases` must explicitly set `updated_at = NOW()`.

5. **text_hash unique index** — enforces dedup at DB level. Pipeline handles UniqueViolation by treating it as successful dedup (returns existing case_id).

## Start Now

Read the checklist file and begin with the first unchecked item.
