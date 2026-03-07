# Quality Overhaul Design — Phase 6.6

## Context

A comprehensive quality audit of Smriti found **34 gaps** across 5 areas (search, RAG chat, agents, frontend, components). While all 461 backend and 156 frontend tests pass, the tests validate code correctness — not lawyer-grade output quality. The gaps range from broken core features (citation graph expansion silently returning zero results) to missing UX signals (ConfidenceMeter built but never deployed).

**Goal**: Fix all 34 gaps to make Smriti's output quality competitive with Harvey AI and Jhana AI. Organized into 4 waves by dependency order.

---

## Wave 1: Backend Foundations

Fixes that other fixes depend on. All backend-only.

### 1.1 Fix Citation Graph Expansion (Gap 1) — CRITICAL
**Problem**: `deep_precedent_search_node` reads `neighbors.get("nodes", [])` but `Neo4jGraph.get_neighbors` returns key `"neighbors"`. Each element is `{"node": {...}, "relationship": ...}` not a flat dict. Result: 2-hop graph expansion silently produces zero results.

**Fix**:
- File: `backend/app/core/agents/nodes/case_prep_nodes.py`
- Change `neighbors.get("nodes", [])` → `neighbors.get("neighbors", [])`
- Change `node.get("id")` → `node.get("node", {}).get("id")` and similar for title/citation/court/year
- Add unit test that verifies graph-sourced cases appear in results

### 1.2 Feed HITL Feedback into Decompose (Gap 4) — CRITICAL
**Problem**: `decompose_query_node` only reads `classification` messages, ignoring `user_feedback` messages. User corrections at checkpoint have no effect.

**Fix**:
- File: `backend/app/core/agents/nodes/research_nodes.py` (`decompose_query_node`)
- After reading classification, scan messages for `{"type": "user_feedback", "step": "plan"}` and include feedback text in the decompose prompt: "The user has requested the following adjustments: {feedback}"
- Add unit test: decompose with feedback message in state produces different sub-queries

### 1.3 Fill Precedent Strengths (Gap 5) — CRITICAL
**Problem**: `precedent_strengths` is hardcoded `[]` in `synthesize_memo_node`. Authority component always defaults to 0.3.

**Fix**:
- File: `backend/app/core/agents/nodes/research_nodes.py` (`synthesize_memo_node`)
- After gathering results (which are now enriched with `bench_type` via `enrich_results_with_ratio`), call `classify_precedent_strength` for each result and pass the list to `calculate_confidence`
- Need: source court from result, target court (from query or default "Supreme Court of India"), bench_type from enrichment
- Add unit test: confidence score differs when results have "constitutional" vs "single" bench_type

### 1.4 Human-Readable Citation Verification (Gap 2) — CRITICAL
**Problem**: `verify_citations_node` only checks UUID patterns. LLMs write human-readable citations like "(2023) 5 SCC 123" which are never verified.

**Fix**:
- File: `backend/app/core/agents/nodes/common.py` (new function `verify_human_citations`)
- Extract citation patterns from memo text using existing `CITATION_PATTERNS` from `core/legal/extractor.py`
- Query `cases.citation ILIKE` and `case_citation_equivalents.citation_text ILIKE` for each extracted citation
- Also check: is this citation in the search results that were passed as context? (grounding check)
- Return: list of unverified citations (not in DB) and ungrounded citations (in DB but not in search results)
- Update `verify_citations_node` in both research and case prep agents to call this
- Add warnings to memo output for unverified citations
- Add unit tests

### 1.5 Surface Vector Chunk Passages (Gap 8) — HIGH
**Problem**: Pinecone returns chunk-level matches with the actual relevant passage, but after case-level deduplication the chunk text is discarded. RAG context uses `ratio_decidendi` (ingestion-time summary) instead of the matched passage.

**Fix**:
- File: `backend/app/core/search/hybrid.py` (`_vector_search`, `_deduplicate_by_case`)
- Store the best chunk's `metadata.text` (or `metadata.chunk_text`) alongside the score during deduplication
- Add `chunk_text` field to `SearchResultItem` dataclass
- File: `backend/app/core/chat/rag.py` (`_build_sources`)
- Use `chunk_text` as "Relevant Passage" when available, falling back to FTS snippet then ratio_decidendi
- Add unit test

### 1.6 Fix Reranker Snippet for Vector-Only Hits (Gap 9) — HIGH
**Problem**: When a case appears only in vector results (not FTS), `_build_snippets_map` has no entry, and the reranker receives the case_id UUID string.

**Fix**:
- File: `backend/app/core/search/hybrid.py` (`_build_snippets_map`)
- Include vector result chunk_text (from 1.5) in the snippets map
- Fallback chain: FTS headline → vector chunk_text → case title → case_id
- Add unit test

### 1.7 Multi-Turn Query Reformulation (Gap 10) — HIGH
**Problem**: Follow-up queries like "and the penalty?" are searched literally without conversation context.

**Fix**:
- File: `backend/app/core/chat/rag.py` (`rag_respond`)
- Before calling `understand_query`, check if there are previous messages in history
- If yes, use a lightweight LLM call (Gemini Flash) to reformulate the query with context: "Given the conversation about [topic], the user now asks: 'and the penalty?' → Reformulated: 'penalty provisions in income tax law'"
- Add the reformulated query to `understand_query` call
- Add unit test with mock conversation history

---

## Wave 2: Safety & Trust

Accuracy features that lawyers depend on for correctness.

### 2.1 Overruled Case Detection (Gap 3) — CRITICAL
**Problem**: `PrecedentStrength.OVERRULED` exists in enum but is never assigned. No code detects whether a case has been overruled.

**Fix** (pragmatic approach for current data scale):
- File: `backend/app/core/legal/treatment.py` (new)
- During ingestion, scan judgment text for treatment language: "overruled", "no longer good law", "per incuriam", "distinguished", "affirmed", "followed", "explained"
- Use regex patterns + LLM classification (Gemini Flash) to identify treatment of cited cases
- Store as `citation_treatment` field in Neo4j edges (OVERRULES, DISTINGUISHES, AFFIRMS, FOLLOWS)
- File: `backend/app/core/legal/precedent_strength.py`
- Before returning BINDING, check Neo4j for any `OVERRULES` edge pointing to this case
- If overruled, return OVERRULED with the overruling case citation
- Add migration for `citation_treatments` table (PostgreSQL fallback if Neo4j unavailable)
- Add unit tests

### 2.2 Surface Load Analysis Errors (Gap 6) — HIGH
**Problem**: When `DocumentAnalysis` not found, Case Prep agent continues with empty inputs and produces generic memo with no error surface.

**Fix**:
- File: `backend/app/core/agents/nodes/case_prep_nodes.py` (`load_analysis_node`)
- When analysis not found, set `state["error"] = "No analysis found..."` and return early
- File: `backend/app/core/agents/case_prep.py` (graph routing)
- Add conditional edge: if `state.get("error")`, skip to done with error message
- Add unit test

### 2.3 Label Issue Scores as AI Estimates (Gap 7) — MEDIUM
**Problem**: Issue prioritization scores (legal_strength, relevance, etc.) are LLM-generated without access to search results, but displayed as authoritative.

**Fix**:
- File: `backend/app/core/agents/nodes/case_prep_nodes.py` (`prioritize_issues_node`)
- Add `"note": "AI-estimated scores — will be validated against actual precedents in next step"` to each issue
- After `deep_precedent_search_node`, update scores based on actual results found (e.g., boost legal_strength if 5+ binding cases found)
- Add unit test

### 2.4 Prompt Alignment Fixes — MEDIUM
**Problem**: System prompt expects `[SOURCE 1 - ...]` format but context uses `[1] Case Title / Citation:...`. No "do not supplement from training data" rule. No source-number verification instruction.

**Fix**:
- File: `backend/app/core/legal/prompts.py` (`CHAT_SYSTEM_PROMPT`)
- Update CONTEXT FORMAT section to match actual `_format_context` output: `[1] Case Title (Citation)\n    Court: ... | Year: ...\n    Ratio Decidendi: ...\n    Relevant Passage: ...`
- Add rule: "Do NOT supplement your response with legal knowledge from your training data. Only cite cases and principles from the provided context."
- Add rule: "The numbers [1], [2], etc. in your response MUST correspond exactly to the numbered sources in the context. Do not reference source numbers that do not exist."
- No code test needed — prompt change only

---

## Wave 3: Frontend UX

What lawyers see and interact with.

### 3.1 Chat: Inline Citation Anchors (Gap 7/frontend) — CRITICAL
**Problem**: LLM references like [1], [2] in response text are plain text, not linked to sources.

**Fix**:
- File: `frontend/src/app/chat/page.tsx`
- Parse assistant message text for `[N]` patterns
- Replace with clickable anchor that scrolls to / highlights the corresponding source badge
- Or: render as superscript link to case detail page

### 3.2 Chat: Markdown Rendering (Gap 8/frontend) — CRITICAL
**Problem**: Structured LLM output renders as literal `**bold**` and `## headings`.

**Fix**:
- Install `react-markdown` + `remark-gfm`
- File: `frontend/src/app/chat/page.tsx`
- Replace `<p className="whitespace-pre-wrap">` with `<ReactMarkdown>` for assistant messages
- Style with Tailwind prose classes

### 3.3 Chat: Confidence Signal (Gap 9) — HIGH
- Add confidence score to RAG response SSE events
- Display `ConfidenceMeter` under each assistant message

### 3.4 Chat: Copy/Export (Gap 11) — MEDIUM
- Add "Copy" button (clipboard) on each assistant message
- Add "Export as Markdown" for full session

### 3.5 Chat: Session Rename (Gap 10/frontend) — MEDIUM
- Make session title editable in sidebar (click → input → save)

### 3.6 Chat: Source Badges with Court+Year (Gap 12) — MEDIUM
- Show `citation || title` + `court` + `year` on source badges

### 3.7 Search: Deploy ConfidenceMeter (Gap 18) — HIGH
- Replace raw score number with `ConfidenceMeter` on each result card

### 3.8 Search: First-Class Section Filter (Gap 2/frontend) — HIGH
- Move section filter out of collapsed panel into horizontal pill tabs above results
- Always visible, one-click activation

### 3.9 Search: Auto-Apply Filters (Gap 3/frontend) — MEDIUM
- Trigger re-search on filter change (debounced 300ms)

### 3.10 Search: Judge & Act Filters (Gap 4/frontend) — MEDIUM
- Add judge name autocomplete and act/section filter to filter panel

### 3.11 Search: Section Labels on Snippets (Gap 5/frontend) — MEDIUM
- Show `[HOLDINGS]` or `[RATIO]` pill before snippet text when section data available

### 3.12 Search: Minimum Score / No Results Signal — MEDIUM
- When all results score below 0.3, show "No highly relevant results found" banner

### 3.13 Case Detail: Inline Citation Links (Gap 27) — HIGH
- Parse judgment text for citation patterns, link to `/case/[id]` when case exists in DB

### 3.14 Case Detail: Relationship Labels (Gap 30) — HIGH
- Show "Approved", "Distinguished", "Overruled" badges on cited-by entries (requires Wave 2.1 data)

### 3.15 Case Detail: "Open in Chat" (Gap 33) — MEDIUM
- Add button that opens `/chat` with pre-filled query about this case

### 3.16 Case Detail: Graph Legend (Gap 31) — LOW
- Add 3-line legend: arrow direction, node size, gold = current case

### 3.17 Case Detail: Hide Chunk Count (Gap 34) — LOW
- Replace `chunk_count` with estimated word count or page count

### 3.18 Case Detail: Cited By with Court+Year (Gap 29) — LOW
- Add court and year to cited-by entries (same as "Cases Cited" section)

### 3.19 Components: BenchStrength Visual Hierarchy (Gap 14) — MEDIUM
- Constitutional Bench: bold + blue badge. Full Bench: semi-bold. Division: normal. Single: muted.

### 3.20 Components: Precedent Tooltips (Gap 13) — LOW
- Add tooltip explaining each precedent strength level

### 3.21 Components: Individual Citation Copy (Gap 15) — LOW
- Click citation → copy to clipboard

### 3.22 Components: Disclaimer Sticky on Mobile (Gap 17) — LOW
- Make LegalDisclaimer sticky-bottom on mobile viewports

---

## Wave 4: Agent UX Polish

### 4.1 Human-Readable Step Names (Gap 19) — HIGH
- Map internal names to user-facing labels:
  - classify → "Understanding your question"
  - decompose → "Breaking into sub-questions"
  - checkpoint_plan → "Review research plan"
  - search → "Searching case law"
  - gather → "Analyzing judgments"
  - contradictions → "Checking for conflicts"
  - checkpoint_findings → "Review findings"
  - synthesize → "Drafting research memo"
  - verify → "Verifying citations"
  - checkpoint_memo → "Final review"

### 4.2 Sub-Progress During Search (Gap 20) — MEDIUM
- During `search` step, show "Searched 3 of 7 sub-questions" via SSE progress events
- Requires backend to emit progress events during parallel_search_node

### 4.3 Pre-Populated Checkpoint Suggestions (Gap 21) — MEDIUM
- Add 2-3 example responses as clickable chips above the textarea

### 4.4 Resolve UUID Links to Case Titles (Gap 22) — HIGH
- In AgentMemoViewer, detect UUIDs and fetch titles via API, display as `[Case Title (Citation)]`

### 4.5 Memo Export (Gap 23) — MEDIUM
- Add "Copy to Clipboard" and "Download as Markdown" buttons on memo

### 4.6 Header/Footer on Agent Pages (Gap 24) — LOW
- Wrap agent pages in the standard layout with Header and Footer

### 4.7 Better Document Picker (Gap 25) — LOW
- Card-based picker with filename, upload date, key facts snippet, analysis status

### 4.8 Case Prep Preview (Gap 26) — LOW
- Add example output preview or "What you'll get" section before starting

---

## Verification Plan

After each wave:
1. Run `python -m pytest tests/unit/ -v` — all tests pass
2. Run `npx vitest run` — all tests pass
3. Run `npx next build` — clean build
4. Manual smoke test of affected features

After all waves:
1. Run 10 golden queries through search, verify result quality
2. Run 3 research agent sessions, verify memo cites real cases
3. Run 1 case prep session, verify graph expansion returns results
4. Verify chat markdown renders correctly
5. Verify inline citations link to correct sources

---

## Files to Modify

### Backend (Wave 1-2)
- `backend/app/core/agents/nodes/case_prep_nodes.py` — graph key fix, load_analysis error, score labeling
- `backend/app/core/agents/nodes/research_nodes.py` — HITL feedback, precedent strengths, citation verification
- `backend/app/core/agents/nodes/common.py` — human-readable citation verification function
- `backend/app/core/search/hybrid.py` — chunk text preservation, reranker snippets
- `backend/app/core/chat/rag.py` — chunk text in context, multi-turn reformulation
- `backend/app/core/legal/prompts.py` — prompt alignment, anti-supplementation rule
- `backend/app/core/legal/precedent_strength.py` — overruled detection
- `backend/app/core/legal/treatment.py` — new: citation treatment extraction
- `backend/app/core/agents/case_prep.py` — error routing

### Frontend (Wave 3-4)
- `frontend/src/app/chat/page.tsx` — markdown, inline citations, confidence, copy, rename
- `frontend/src/app/search/page.tsx` — ConfidenceMeter, section filter, auto-apply, judge/act filters
- `frontend/src/app/case/[id]/page.tsx` — inline links, relationship labels, Open in Chat, legend
- `frontend/src/app/agents/research/page.tsx` — step names, sub-progress, checkpoint suggestions, export
- `frontend/src/app/agents/case-prep/page.tsx` — same as research + document picker
- `frontend/src/components/bench-strength.tsx` — visual hierarchy
- `frontend/src/components/precedent-badge.tsx` — tooltips
- `frontend/src/components/confidence-meter.tsx` — no changes (already built)
- `frontend/src/components/equivalent-citations.tsx` — copy button
- `frontend/src/components/legal-disclaimer.tsx` — mobile sticky
- `frontend/src/components/agent-memo-viewer.tsx` — UUID → title resolution, export
- `frontend/src/components/agent-step-timeline.tsx` — human-readable names
