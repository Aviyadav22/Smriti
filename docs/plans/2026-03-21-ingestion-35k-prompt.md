# Opus Ralph-Loop Prompt — Ingestion 35K Hardening

> **Copy everything below this line and paste into a fresh Claude Code terminal.**

---

You are implementing the Ingestion 35K Hardening plan for the Smriti legal research platform. This is a systematic implementation loop — you will implement one step at a time, verify it, and check it off.

## Your Files

1. **Plan** (full implementation details, code snippets, E2E impact analysis):
   `docs/plans/2026-03-21-ingestion-35k-hardening.md`

2. **Checklist** (your tracking file — update checkboxes as you complete steps):
   `docs/plans/2026-03-21-ingestion-35k-checklist.md`

## Your Loop

For each iteration:

1. **Read the checklist** (`docs/plans/2026-03-21-ingestion-35k-checklist.md`) to find the first unchecked `[ ]` item.
2. **Read the plan** (`docs/plans/2026-03-21-ingestion-35k-hardening.md`) for the corresponding phase/step to get full implementation details and code snippets.
3. **Read the E2E notes** in the checklist for that step — they describe cross-step dependencies and what to watch for.
4. **Read the target file(s)** to understand current code before making changes.
5. **Implement the change** exactly as described in the plan. Do not skip steps or combine multiple steps.
6. **Run verification** as described in the checklist item (grep, test, or query).
7. **Run the full test suite** after each step: `cd backend && python -m pytest tests/unit/ --tb=short -q` — fix any failures before proceeding.
8. **Update the checklist**: change `[ ]` → `[x]` for the completed step.
9. **Repeat** from step 1.

## Rules

- **One step at a time.** Do not batch multiple steps. Each step has been designed with E2E dependencies in mind.
- **Read before writing.** Always read the target file before editing. Understand existing code.
- **Tests must pass.** If the test suite fails after a step, fix it before moving to the next step. Do NOT skip failing tests.
- **Follow the plan's code.** The plan has specific code snippets — use them as the primary reference. Adapt line numbers (they may have shifted from prior edits).
- **Check E2E notes.** Each step's E2E section warns about cross-cutting effects. Read it.
- **Do not over-engineer.** Only implement what the plan specifies. No additional refactoring, no extra features.
- **Migration chain.** Migration 025 has `down_revision = "024"`. Migration 026 has `down_revision = "025"`. Do not break the chain.
- **Commit after each phase** (not each step). After completing all steps in a phase, commit with a descriptive message.

## Context

- **Project**: Smriti — AI-powered Indian legal research platform
- **Stack**: FastAPI + PostgreSQL + Pinecone + Neo4j + Gemini
- **What happened**: A 7-agent deep audit found 45 issues (7 CRITICAL, 16 HIGH, 22 MEDIUM) that would cause failures during continuous 35K case ingestion
- **Goal**: Fix all issues so the pipeline can reliably ingest 35,000 Supreme Court cases
- **Current state**: 1984 tests passing, migration at 024, 2 test cases ingested from 2020
- **Key files**:
  - `backend/app/core/ingestion/pipeline.py` — core ingestion pipeline
  - `backend/scripts/ingest_s3.py` — orchestration/workers
  - `backend/app/core/ingestion/metadata.py` — LLM metadata extraction
  - `backend/app/core/ingestion/pdf.py` — PDF text extraction/cleaning
  - `backend/app/core/ingestion/contextual_embeddings.py` — contextual prefix generation
  - `backend/app/core/providers/embeddings/gemini.py` — Gemini embedder
  - `backend/app/core/providers/graph/neo4j_store.py` — Neo4j graph store
  - `backend/app/core/config.py` — settings
  - `backend/app/models/case.py` — SQLAlchemy Case model

## Start Now

Read the checklist file and begin with the first unchecked item.
