# Research Pipeline Audit — Consolidated Fix Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all critical and high-severity bugs found across 10 parallel audit subagents analyzing the research agent pipeline end-to-end.

**Architecture:** Fixes are grouped into 4 tiers by severity. Each task is independent unless noted. Backend changes require restart after ingestion completes.

**Tech Stack:** Python (FastAPI, LangGraph), TypeScript (Next.js, React), PostgreSQL

---

## Severity Tiers

### TIER 1 — CRITICAL (Data loss / Feature broken)

These bugs mean footnotes fundamentally don't work in many scenarios.

### Task 1: Fix citation lookup keying — footnotes silently empty

**Problem:** `format_footnotes_node` uses exact citation string matching (`citation_lookup[cite_text]`) to connect LLM footnote references to worker results. The LLM's citation text almost never exactly matches the key in `citation_lookup` (e.g., `"AIR 1973 SC 1461"` vs `"State of Karnataka v. Dr. Praveen Bhai Togadia, AIR 1973 SC 1461"`). Result: footnotes array is populated but every footnote has `verification_status: "unverified"`, no `case_id`, no `ik_doc_id`, no `pdf_available`.

**Files:**
- Modify: `backend/app/core/agents/research_nodes.py` — `format_footnotes_node` function

**Fix:** Replace exact-match lookup with fuzzy/substring matching:
1. Build a reverse index from citation_lookup: for each entry, extract normalized substrings (reporter citations like `AIR 1973 SC 1461`, neutral citations like `2023:INSC:100`, case names)
2. When matching LLM footnote citation text, try: exact match → normalized substring match → fuzzy ratio > 0.85
3. Log match quality for debugging

**Step 1:** Read the current `format_footnotes_node` implementation to understand exact data structures

**Step 2:** Write failing test — footnote with partial citation text should still match

**Step 3:** Implement fuzzy citation matching with fallback chain: exact → substring → fuzzy

**Step 4:** Run tests, verify pass

**Step 5:** Commit

---

### Task 2: Fix statute/web/community results invisible to footnotes

**Problem:** Only case law results have a `citation` field. Statute sections, web results, and community sources have no `citation` key, so they're completely excluded from `citation_lookup` dict. The LLM references them in footnotes but they can never be enriched.

**Files:**
- Modify: `backend/app/core/agents/research_nodes.py` — citation_lookup building logic

**Fix:** Generate synthetic citation keys for non-case sources:
- Statute: use `f"{act_name} Section {section}"` as key
- Web: use URL or title as key
- Add these to `citation_lookup` so format_footnotes can match them

**Step 1:** Read how citation_lookup is built (which worker results feed into it)

**Step 2:** Write failing test — statute footnote should get enriched with source data

**Step 3:** Add statute/web entries to citation_lookup with appropriate keys

**Step 4:** Run tests, verify pass

**Step 5:** Commit

---

### Task 3: Fix fast path prompt missing [^N] format specification

**Problem:** The fast path synthesis prompt doesn't instruct the LLM to use `[^N]` footnote format. When the query is classified as "simple" and routed through fast path, the synthesized memo may contain zero footnote markers, making the downstream `format_footnotes` node produce an empty footnotes list.

**Files:**
- Modify: `backend/app/core/agents/research_nodes.py` — `fast_path_synthesis_node` prompt

**Fix:** Add explicit footnote format instructions to the fast path synthesis prompt, matching the full-path synthesis prompt's format.

**Step 1:** Read both `fast_path_synthesis_node` and full `synthesize_node` prompts

**Step 2:** Write test — fast path synthesis output should contain `[^N]` markers

**Step 3:** Add footnote format instructions to fast path prompt

**Step 4:** Run tests, verify pass

**Step 5:** Commit

---

### Task 4: Fix IK results getting empty source_url

**Problem:** Indian Kanoon search results have `ik_doc_id` but the `source_url` field is set to `""`. No code path ever generates the IK URL (`https://indiankanoon.org/doc/{ik_doc_id}/`) from the doc ID. Footnotes for IK-sourced cases show no "View on Indian Kanoon" link.

**Files:**
- Modify: `backend/app/core/agents/research_nodes.py` — IK worker result processing

**Fix:** When building citation_lookup entries from IK results, set `source_url = f"https://indiankanoon.org/doc/{ik_doc_id}/"` if source_url is empty and ik_doc_id is present.

**Step 1:** Find where IK results are processed into citation_lookup

**Step 2:** Write failing test — IK result should have source_url populated

**Step 3:** Add URL generation from ik_doc_id

**Step 4:** Run tests, verify pass

**Step 5:** Commit

---

### TIER 2 — HIGH (Feature degraded / UX broken)

### Task 5: Fix cached responses — UI stuck in running state

**Problem:** When a query hits the agent cache, the response is returned as a single JSON blob, not as SSE events. The frontend never receives a `done` event, so `isRunning` stays `true` forever. The user sees a perpetual spinner.

**Files:**
- Modify: `backend/app/api/routes/agents.py` — cached response handling
- Modify: `frontend/src/app/agents/research/page.tsx` — cached response handling

**Fix (backend):** When serving cached response, emit proper SSE event sequence: `status` → `memo` (with footnotes/audit) → `done`

**Fix (frontend):** Alternatively/additionally, detect non-SSE JSON response and handle it directly.

**Step 1:** Read the cache hit code path in agents.py

**Step 2:** Write test for cached response emitting proper SSE sequence

**Step 3:** Implement SSE event sequence for cached responses

**Step 4:** Run tests, verify pass

**Step 5:** Commit

---

### Task 6: Fix false-positive footnote matching in memo viewer

**Problem:** The regex `\[(\d+)\]` matches legal paragraph references like `[Para 15]` → no, but `[15]` in "Section 302 [15]" context, year citations `[1973]`, and numbered lists `[1]`, `[2]`. Users see random numbers highlighted as clickable footnotes when they're not.

**Files:**
- Modify: `frontend/src/app/agents/research/page.tsx` — footnote pill regex in memo rendering

**Fix:** Change regex to only match `[^N]` caret-prefixed format (matching what we tell the LLM to produce), or validate that N is within the actual footnotes range.

**Step 1:** Read the memo rendering code that creates footnote pills

**Step 2:** Update regex to `\[\^(\d+)\]` to match only caret-prefixed footnotes

**Step 3:** Also validate the number is within `footnotes.length` range

**Step 4:** Verify with manual test

**Step 5:** Commit

---

### Task 7: Fix memo viewer — no markdown rendering

**Problem:** The memo content is rendered as plain text. Bold (`**text**`), italic, bullet lists, headers, and code blocks all appear as raw markdown syntax. The chat interface uses react-markdown but the research memo viewer doesn't.

**Files:**
- Modify: `frontend/src/app/agents/research/page.tsx` — memo display section

**Fix:** Wrap memo content in `<ReactMarkdown>` with `remarkGfm` plugin (already used in chat), but preserve the footnote pill replacement logic by processing markdown output.

**Step 1:** Read how chat uses react-markdown (already in project deps)

**Step 2:** Add ReactMarkdown to memo viewer, keeping footnote pill logic

**Step 3:** Verify rendering with sample markdown memo

**Step 4:** Commit

---

### Task 8: Remove dead graph nodes (synthesize, verify)

**Problem:** `synthesize` and `verify` nodes are registered in the graph but have no incoming edges — completely unreachable dead code. They were replaced by `synthesize_v2` and `verify_v2` but never removed.

**Files:**
- Modify: `backend/app/core/agents/research.py` — graph builder

**Fix:** Remove the dead node registrations and their associated functions if unused elsewhere.

**Step 1:** Verify nodes are truly unreachable (grep for references)

**Step 2:** Remove dead nodes from graph builder

**Step 3:** Run tests, verify pass

**Step 4:** Commit

---

### TIER 3 — MEDIUM (Edge cases / Polish)

### Task 9: Fix memo SSE event missing source_attribution and legal_quality_result

**Files:**
- Modify: `backend/app/api/routes/agents.py` — memo event data building

**Fix:** Include `source_attribution`, `legal_quality_result`, `contradictions` in memo_event_data if present in final state.

---

### Task 10: Fix frontend ResearchAudit type missing source_counts

**Files:**
- Modify: `frontend/src/lib/types.ts` — ResearchAudit interface

**Fix:** Add `source_counts?: Record<string, number>` to match backend schema.

---

### Task 11: Fix checkpoint_memo payload — empty user response silently proceeds

**Files:**
- Modify: `backend/app/core/agents/research.py` — checkpoint resume handling

**Fix:** When user provides empty/whitespace response at memo checkpoint, treat as "approved" explicitly rather than passing empty string to synthesis.

---

### Task 12: Fix "Bench:" label semantics in CasePreview

**Files:**
- Modify: `frontend/src/components/footnote-preview.tsx` — CasePreview component

**Fix:** When `author` is present, show "Author: {author}" and "Bench: {bench}" separately. When only bench, show "Bench: {bench}".

---

### Task 13: Fix handleReset not clearing checkpointError

**Files:**
- Modify: `frontend/src/app/agents/research/page.tsx` — handleReset function

**Fix:** Add `setCheckpointError(null)` to handleReset.

---

### Task 14: Add fast path entries to RESEARCH_STEPS for timeline

**Files:**
- Modify: `frontend/src/app/agents/research/page.tsx` — RESEARCH_STEPS constant

**Fix:** Add step entries for `fast_path_search` and `fast_path_synthesis` so the progress timeline doesn't skip when fast path is used.

---

### TIER 4 — LOW (Nice to have)

### Task 15: Self-host pdfjs worker instead of unpkg CDN

**Files:**
- Modify: `frontend/src/components/pdf-viewer.tsx`

**Fix:** Copy pdfjs worker to `public/` and reference locally instead of unpkg CDN (fails in restricted networks).

---

### Task 16: Add untyped fields to AgentStreamEvent

**Files:**
- Modify: `frontend/src/lib/types.ts`

**Fix:** Type `context` and `data` fields on `AgentStreamEvent`.

---

## Execution Order

**Recommended:** Tasks 1-4 (Tier 1) first — these fix the core footnotes pipeline. Then Tasks 5-8 (Tier 2) for UX. Then Tier 3-4 as time allows.

Tasks 1 and 2 are closely related (both touch citation_lookup) — do them together.
Tasks 6 and 7 are closely related (both touch memo rendering) — do them together.
All other tasks are independent.
