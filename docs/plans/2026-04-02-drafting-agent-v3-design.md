# Drafting Agent V3 — Implementation Plan

## Context

V2 of the Drafting Agent is complete with 17 document types, court formatting profiles, BNS/BNSS/BSA mappings, CRAC/IRAC modes, 4 differentiating features (overruled shield, citation graph suggestions, statute injection, affidavit gen), and a research-to-draft bridge. V3 adds 6 major features that will make Smriti the most complete legal drafting platform in India — no competitor (Jhana, VakilAI, Satya.ai, or even Harvey's SCC partnership) offers all of these together.

**Key research finding:** No Indian court provides e-filing submission APIs — the correct strategy is generating filing-ready PDFs that pass court validation. This is a genuine green field nobody fills.

**Key competitive insight:** Learned Hand (LA County, 10 US states) adapts drafts to judge writing style. No Indian tool does this. Smriti already has judge analytics (Phase 4) with disposal_patterns, judicial_tone, key_observations — we just need to wire it into drafting prompts.

---

## V3 Feature Scope (6 features + 4 bonus utilities)

### Priority Tiers

**Tier 1 — High Impact, Moderate Effort (build first):**
1. Upload Opposing Document → Auto-Generate Response
2. Judge-Aware Drafting
3. Filing-Ready PDF Export (court-specific validation)

**Tier 2 — High Impact, Higher Effort:**
4. Hindi/Bilingual Drafting
5. Version Tracking / Diff View

**Tier 3 — Moderate Impact, Lower Effort (bonus utilities):**
6. User Clause Libraries / Precedent Banks
7. Limitation Period Calculator
8. Cross-Document Consistency Checker
9. Filing Package Generator (main doc + affidavit + vakalatnama + index)
10. Court Fee Estimator

---

## Feature 1: Upload Opposing Document → Auto-Generate Response

### Approach
Two-phase pipeline using existing PDF extraction + a new LLM-powered document parser:

**Phase A — Structural Extraction:**
1. User uploads PDF (existing `POST /upload` endpoint, 50MB limit)
2. Extract text via `extract_pdf_text()` from `backend/app/core/ingestion/pdf.py`
3. New LLM node: parse extracted text into structured JSON (parties, facts per paragraph, prayers, legal grounds, statutory provisions, chronology)
4. User reviews/edits the parsed structure at a HITL checkpoint

**Phase B — Response Generation:**
1. Map input doc type to response type:
   - Plaint → Written Statement (para-wise reply)
   - Legal Notice → Reply to Legal Notice
   - Impugned Order → Appeal / SLP
   - Charge Sheet → Discharge Application
   - Bail Rejection Order → Appeal against Bail Rejection
2. Pre-populate DraftingState with extracted facts, provisions, and opposing arguments
3. Run existing drafting graph with enriched initial state
4. For Written Statement specifically: generate para-wise reply ("admitted/denied/not admitted" for each paragraph)

### New Graph Node
Add `parse_opposing_document_node` BEFORE `resolve_template` — only runs when `opposing_document_id` is present in state. Otherwise, the graph flows as before (backwards compatible).

```
START → [parse_opposing_document (if doc uploaded)] → resolve_template → ...existing flow...
```

### Files to Create/Modify
- **Create:** `backend/app/core/drafting/document_parser.py` — LLM-powered structural extraction
- **Modify:** `backend/app/core/agents/nodes/drafting_nodes.py` — add `parse_opposing_document_node`
- **Modify:** `backend/app/core/agents/state.py` — add `opposing_document_id`, `parsed_opposing_doc` to DraftingState
- **Modify:** `backend/app/core/agents/drafting.py` — conditional edge for document parsing
- **Modify:** `backend/app/api/routes/agents.py` — new `/drafting/from-document` endpoint
- **Modify:** `frontend/src/app/agents/drafting/page.tsx` — file upload UI + parsed doc review
- **Create:** `backend/tests/unit/test_document_parser.py`

### Key Reuse
- `extract_pdf_text()` from `ingestion/pdf.py` — text extraction
- `POST /upload` from `documents.py` — file upload + GCS storage
- Existing drafting graph — response generation
- `sanitize_search_query()` — input sanitization

### API
```
POST /api/agents/drafting/from-document
{
    "document_id": "uuid-of-uploaded-doc",
    "response_type": "written_statement",  // or auto-detect
    "target_court": "Delhi High Court",
    "additional_context": {...}
}
Returns: SSE stream
```

---

## Feature 2: Judge-Aware Drafting

### Approach
Query existing judge analytics when `bench_composition` is provided, inject judge-specific context into drafting prompts. This is low-effort because all the analytics infrastructure exists.

### How It Works
1. User optionally provides `bench_composition: list[str]` (judge names) in the drafting request
2. `resolve_template_node` queries `JudgeAnalyticsService.get_judge_profile()` for each judge
3. Optionally runs `predict_outcome()` for the case type + judges
4. Builds a `judge_context` string injected into `draft_sections_node` prompts:

```
Judge Context (optional — use to calibrate argument emphasis):
- Hon'ble Justice X: Tends to favor [disposal_patterns]. Key observations in similar cases: [key_observations].
  Judicial tone: [judicial_tone]. Frequently cites: [top_cited_judgments].
- Outcome prediction: [predicted_outcome] (confidence: [confidence], based on [sample_size] similar cases)
  Strongest factors: [factors]
```

### Files to Modify
- **Modify:** `backend/app/core/agents/state.py` — add `bench_composition: list[str]`, `judge_context: dict`
- **Modify:** `backend/app/core/agents/nodes/drafting_nodes.py` — query judge analytics in `resolve_template_node`, inject into `draft_sections_node`
- **Modify:** `backend/app/api/routes/agents.py` — add `bench_composition` to `DraftingRequest`
- **Modify:** `frontend/src/app/agents/drafting/page.tsx` — judge name input field

### Key Reuse
- `JudgeAnalyticsService.get_judge_profile()` from `analytics/judge_analytics.py`
- `predict_outcome()` from `analytics/judge_prediction.py`
- Neo4j judge data (AUTHORED_BY/DECIDED_BY relationships)
- Case model fields: `judicial_tone`, `key_observations`, `disposal_patterns`

### Privacy Note
Frame as "calibrating argument emphasis" not "predicting the judge." Include disclaimer in output.

---

## Feature 3: Filing-Ready PDF Export

### Approach
Upgrade the existing export engine to generate court-specific compliant PDFs that pass e-filing validation. This is the most technically differentiating feature — nobody in India does this.

### Court-Specific Requirements Matrix

| Court | PDF Format | Max Size | DPI | Bookmarks | OCR | DSC |
|-------|-----------|----------|-----|-----------|-----|-----|
| SC | PDF 1.7+ | 50 MB | 200 text / 300 scan | Required | No | Class III |
| Delhi HC | PDF | 50 MB online | - | Required | No | Class III / Aadhaar eSign |
| Bombay HC | PDF/A | - | 300 | Required | Required | Class III |
| NCLT | PDF/A | 20 MB | - | Master Index | Required | Class III |

### Implementation
1. **PDF/A conversion**: Use `pikepdf` to convert ReportLab output to PDF/A-2b (embeds fonts, strips encryption)
2. **Bookmarking**: Auto-generate PDF bookmarks from section headings (ReportLab `canvas.bookmarkPage()`)
3. **OCR layer**: Use `ocrmypdf` to add OCR text layer when needed (Bombay HC, NCLT)
4. **Validation**: Pre-export checklist — verify file size, page count, font embedding, bookmark tree, margin compliance
5. **Filing checklist**: Auto-generate a human-readable pre-filing checklist (court fees, limitation, parties, annexures)

### Files to Create/Modify
- **Create:** `backend/app/core/drafting/pdf_compliance.py` — PDF/A conversion, bookmarking, OCR, validation
- **Modify:** `backend/app/core/drafting/export.py` — integrate compliance pipeline after PDF generation
- **Modify:** `backend/app/core/drafting/court_profiles.py` — add `pdf_format`, `requires_ocr`, `max_file_size_mb`, `requires_bookmarks` fields to CourtProfile
- **Create:** `backend/tests/unit/test_pdf_compliance.py`

### New Dependencies
- `pikepdf` — PDF/A conversion, bookmark manipulation
- `ocrmypdf` — OCR text layer (optional, only for Bombay HC/NCLT profiles)

---

## Feature 4: Hindi/Bilingual Drafting

### Approach
Phased: start with English draft → Hindi translation (leveraging existing GeminiTranslator), then evolve to direct Hindi drafting.

**Phase A (V3):** Post-draft translation
1. After `assemble_document_node` produces the English draft, optionally translate to Hindi
2. Use `GeminiTranslator.translate()` with legal terminology preservation (already built)
3. Maintain a Hindi legal glossary for consistent terminology
4. Export bilingual PDF: English on left column, Hindi on right (or sequential pages)

**Phase B (future):** Direct Hindi drafting
- Hindi-specific prompts in `prompts.py` with Devanagari legal terminology
- Requires Hindi legal corpus for quality grounding

### Files to Create/Modify
- **Create:** `backend/app/core/drafting/hindi_glossary.py` — Legal Hindi terminology map (500+ terms)
- **Modify:** `backend/app/core/agents/nodes/drafting_nodes.py` — add translation step after assembly when language="hi"
- **Modify:** `backend/app/core/drafting/export.py` — bilingual DOCX/PDF layout
- **Modify:** `frontend/src/app/agents/drafting/page.tsx` — language toggle with preview

### Key Reuse
- `GeminiTranslator` from `providers/translation/gemini_translator.py`
- `apply_language_suffix()` from `agents/nodes/common.py` (already adds Hindi instruction)
- `next-intl` with `hi.json` messages (frontend already set up)

---

## Feature 5: Version Tracking / Diff View

### Approach
Store revision history in the AgentExecution model. Frontend shows timeline + section-level diff.

### Implementation
1. **Backend:** Each time `revise_section_node` runs, store a snapshot:
   ```python
   # In DraftingState:
   revision_history: list[dict]  # [{version: 1, timestamp, section, old_text, new_text, feedback}]
   ```
2. **API:** New endpoint `GET /drafting/{execution_id}/versions` returns revision history
3. **Frontend:** Use `jsdiff` library for character-level diff rendering. Show:
   - Version timeline (sidebar)
   - Section-level changes (green=added, red=removed)
   - Feedback that triggered each revision
   - "Restore version" button

### Files to Create/Modify
- **Modify:** `backend/app/core/agents/state.py` — add `revision_history: list[dict]`
- **Modify:** `backend/app/core/agents/nodes/drafting_nodes.py` — snapshot before revision
- **Modify:** `backend/app/api/routes/agents.py` — add version history endpoint
- **Create:** `frontend/src/components/draft-diff-viewer.tsx` — diff rendering component
- **Modify:** `frontend/src/app/agents/drafting/page.tsx` — version timeline sidebar

### New Frontend Dependency
- `diff` (npm) — for text diffing

---

## Feature 6: User Clause Libraries / Precedent Banks

### Approach
Users upload past filings → extract argument patterns, prayer formulations, citation preferences → store as embeddings → query during drafting to match firm style.

### Implementation
1. **Upload:** New `POST /clause-library/upload` endpoint — accepts PDF or DOCX
2. **Extraction:** Parse uploaded doc → extract sections → embed each section via Gemini embedder
3. **Storage:** New `clause_library` Pinecone namespace (or metadata filter `vector_type: "user_clause"`)
4. **Query at draft time:** In `draft_sections_node`, before LLM generation, search user's clause library for similar sections. If found, include as "firm-style reference" in the prompt.
5. **Management UI:** List uploaded documents, delete, re-index

### Files to Create/Modify
- **Create:** `backend/app/core/drafting/clause_library.py` — upload, extract, embed, query
- **Create:** `backend/app/api/routes/clause_library.py` — CRUD endpoints
- **Create:** `backend/app/models/clause_library.py` — DB model for uploaded library items
- **Modify:** `backend/app/core/agents/nodes/drafting_nodes.py` — query clause library in draft_sections
- **Create:** `frontend/src/app/clause-library/page.tsx` — management UI
- **Create:** migration for `clause_library_items` table

---

## Bonus Utilities (Low Effort, High Value)

### 7. Limitation Period Calculator
- Input: cause of action type + date of accrual
- Output: limitation period + deadline + whether filing is within time
- Data: Limitation Act 1963 schedule (181 articles) as a lookup table
- Warn at `resolve_template_node` if filing appears time-barred
- **Create:** `backend/app/core/legal/limitation.py`

### 8. Cross-Document Consistency Checker
- When drafting response to an uploaded document, verify:
  - Facts stated in Written Statement don't contradict facts admitted in an earlier filing
  - Dates/amounts are consistent across petition + affidavit
- Run after `assemble_document_node` as a validation step
- **Modify:** `drafting_nodes.py` — add consistency check in `verify_final_node`

### 9. Filing Package Generator
- Export a single ZIP containing: main document + affidavit + vakalatnama template + index of annexures + court fee memo
- **Modify:** `export.py` — add `export_filing_package()` function

### 10. Court Fee Estimator
- Input: suit valuation + state + court level
- Output: court fee amount based on state-specific Court Fees Act
- Start with 5 states (Delhi, Maharashtra, Karnataka, Tamil Nadu, West Bengal)
- **Create:** `backend/app/core/legal/court_fees.py`

---

## Architecture: How V3 Extends V2

### Graph Flow (V3)
```
START → [parse_opposing_document (conditional)] →
  resolve_template (+ judge context + limitation check) →
  gather_provisions → verify_precedents →
  checkpoint_sources (+ suggested precedents) →
  draft_sections (+ clause library + judge calibration + code context) →
  assemble (+ affidavit gen + Hindi translation) →
  checkpoint_draft (+ diff view) →
  (revise loop with version tracking) →
  verify_final (+ consistency check) →
  checkpoint_final (+ filing checklist) →
  [export: filing-ready PDF/DOCX + filing package] → END
```

Only ONE new conditional node added (`parse_opposing_document`). Everything else is enhancement of existing nodes.

### State Schema Additions
```python
# V3 additions to DraftingState:
opposing_document_id: str        # uploaded document UUID
parsed_opposing_doc: dict        # structured extraction of opposing doc
bench_composition: list[str]     # judge names for judge-aware drafting
judge_context: dict              # analytics results for bench
revision_history: list[dict]     # version snapshots for diff view
hindi_draft: str                 # translated Hindi version
filing_checklist: list[dict]     # pre-filing validation results
```

---

## Implementation Order

### Sprint 1: Highest Impact (Features 2, 3, 7, 9, 10)
- Judge-aware drafting (low effort — wire existing analytics)
- Filing-ready PDF export (medium effort — PDF/A, bookmarks, validation)
- Limitation calculator (low effort — lookup table)
- Filing package generator (low effort — ZIP bundling)
- Court fee estimator (low effort — lookup table)

### Sprint 2: Core V3 (Features 1, 5)
- Upload document → auto-generate response (high effort — new parser + graph node)
- Version tracking / diff view (medium effort — snapshots + frontend diff)

### Sprint 3: Language & Libraries (Features 4, 6, 8)
- Hindi/bilingual drafting (medium effort — translation pipeline + glossary)
- Clause libraries (medium effort — new data model + vector search)
- Cross-document consistency checker (low effort — validation in verify_final)

---

## Files Summary

### New Files (10)
| File | Purpose |
|------|---------|
| `backend/app/core/drafting/document_parser.py` | LLM-powered structural extraction of uploaded docs |
| `backend/app/core/drafting/pdf_compliance.py` | PDF/A conversion, bookmarks, OCR, validation |
| `backend/app/core/drafting/hindi_glossary.py` | Legal Hindi terminology map |
| `backend/app/core/drafting/clause_library.py` | User clause library management |
| `backend/app/core/legal/limitation.py` | Limitation Act schedule lookup |
| `backend/app/core/legal/court_fees.py` | State-wise court fee calculator |
| `backend/app/api/routes/clause_library.py` | Clause library CRUD endpoints |
| `backend/app/models/clause_library.py` | DB model for clause library items |
| `frontend/src/components/draft-diff-viewer.tsx` | Diff rendering component |
| `frontend/src/app/clause-library/page.tsx` | Clause library management UI |

### Modified Files (8)
| File | Changes |
|------|---------|
| `backend/app/core/agents/state.py` | +7 V3 fields |
| `backend/app/core/agents/nodes/drafting_nodes.py` | Judge context, clause library query, Hindi translation, consistency check, version snapshots |
| `backend/app/core/agents/drafting.py` | Conditional edge for document parsing |
| `backend/app/core/drafting/export.py` | Filing-ready PDF pipeline, filing package, bilingual export |
| `backend/app/core/drafting/court_profiles.py` | PDF compliance fields |
| `backend/app/api/routes/agents.py` | `/from-document` endpoint, version history endpoint, bench_composition in request |
| `frontend/src/app/agents/drafting/page.tsx` | File upload, judge input, language toggle, diff view, filing checklist |
| `frontend/src/lib/api.ts` | New API functions |

### New Dependencies
- `pikepdf` — PDF/A conversion + bookmarking
- `ocrmypdf` — OCR text layer (optional)
- `diff` (npm) — frontend text diffing

---

## Verification Plan

### Unit Tests
- Document parser: test extraction of plaint structure, notice structure, order structure
- PDF compliance: test PDF/A output, bookmark generation, size validation
- Limitation calculator: test all 181 articles
- Judge context: test with mock judge profiles
- Hindi glossary: test term mapping
- Version history: test snapshot creation and retrieval
- Filing package: test ZIP generation with all components

### Integration Tests
- Upload plaint PDF → extract structure → generate written statement → export filing-ready PDF
- Draft with judge context → verify prompt contains judge-specific instructions
- Draft in Hindi → verify Devanagari output
- Revise section → verify version snapshot created → verify diff endpoint returns changes

### E2E Smoke Test
- Full pipeline: upload opposing document → select response type → add judge names → draft → review → revise → export filing-ready PDF package with affidavit
