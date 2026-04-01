# Drafting Agent V2 — Design Document

**Date:** 2026-04-02
**Status:** Approved
**Scope:** Hybrid expansion — 10 new document types + 3 infrastructure upgrades + 4 differentiating features

---

## 1. Executive Summary

Smriti's Drafting Agent V1 supports 7 document types with a proven LangGraph pipeline (resolve → gather → verify → draft → assemble → revise → verify_final). V2 expands to 17 document types covering ~80% of daily Indian litigation work, adds court-specific formatting profiles, wires in existing BNS/BNSS/BSA amendment mappings, bridges the Research Agent into Drafting, and introduces 4 features no Indian competitor has: overruled precedent shielding, citation graph suggestions, statutory text injection, and companion affidavit auto-generation.

### What V2 Does NOT Include (Deferred to V3)

- Upload opposing document → auto-generate response (plaint → written statement)
- User-uploadable clause libraries / precedent banks
- Judge-aware drafting (adapting tone per bench)
- Hindi/regional language drafting improvements
- E-filing portal integration
- Version tracking / diff view

---

## 2. Competitive Context

### Global Leaders

| Tool | Strength | Gap for India |
|------|----------|--------------|
| Harvey AI ($11B) | Agent Builder, 25K+ custom workflows, MS Word integration | US/UK-focused, $1K+/seat/month, SCC partnership is research-only |
| Lexis+ Protege | 300+ workflows, Shepard's citation verification, 17% hallucination | No Indian drafting formats, no BNS/BNSS support |
| CoCounsel | Westlaw-grounded, playbook-based redlining | 42% accuracy in Stanford benchmark, no Indian law |
| Spellbook | Best-in-class contract drafting in Word | Contracts only, no litigation, no India |

### Indian Competitors

| Tool | Strength | Gap |
|------|----------|-----|
| Jhana AI | 16M+ docs, drafting agents | No citation graph, no court-specific formatting |
| BharatLaw AI | IPC→BNS auto-mapping, Research Book | Research-focused, limited drafting templates |
| VakilAI | Claims court-ready SLP/Writ/Counter Affidavit drafting | No citation verification, no statute DB |
| Satya.ai | Zero-trust verification, 40+ CPC micro-checks | No citation graph, no research-to-draft pipeline |

### Smriti's Unique Advantages

1. **Neo4j citation graph** — structural precedent relationships (followed/overruled/distinguished)
2. **7 Pinecone vector types** — ratio, proposition, headnote, statute, chunk, summary, community
3. **2,932 statute sections** — actual section text for injection
4. **Research Agent V3** → Draft pipeline — seamless flow nobody else has
5. **567 bidirectional amendment mappings** — IPC↔BNS, CrPC↔BNSS, IEA↔BSA already built

---

## 3. Architecture Overview

### Graph Flow (UNCHANGED)

```
START → resolve_template → gather_provisions → verify_precedents →
checkpoint_sources → draft_sections → assemble → checkpoint_draft →
(revise loop) → verify_final → checkpoint_final → END
```

No new nodes. No edge changes. The proven pipeline stays intact.

### New Modules (data, not logic)

- `court_profiles.py` — Court formatting rules as frozen dataclasses
- 10 new entries in `templates.py`
- 10 new prompt constants in `prompts.py`
- Wire `amendment_service` into drafting nodes (already built, 567 mappings)

### Modified Modules

- `drafting_nodes.py` — Inject amendment lookups, citation graph, statute text, CRAC mode, affidavit gen
- `export.py` — Profile-driven formatting instead of hardcoded values
- `agents.py` (routes) — New `/drafting/from-research` + `/drafting/templates` endpoints
- `state.py` — 5 new fields in `DraftingState`
- `drafting.py` — Pass graph_store to verify_precedents closure
- `frontend/src/app/agents/drafting/page.tsx` — Category-grouped selector, affidavit preview

---

## 4. New Document Types (10 additions → 17 total)

### Criminal Litigation

#### 1. Anticipatory Bail (`anticipatory_bail`)

- **Statutory basis:** S.438 CrPC / S.482 BNSS
- **Required fields:** `accused_name`, `fir_number`, `police_station`, `offences_charged`, `apprehension_grounds`
- **Sections:** court_header, case_details, facts_of_the_case, apprehension_of_arrest, grounds_for_anticipatory_bail, legal_provisions, precedents_relied_upon, conditions_offered, prayer, verification
- **Key jurisprudence:** Sushila Aggarwal v. State (NCT of Delhi) (2020) — SC guidelines on anticipatory bail conditions
- **Argument style:** CRAC (advocacy)

#### 2. Quashing Petition (`quashing_petition_482`)

- **Statutory basis:** S.482 CrPC / S.528 BNSS
- **Required fields:** `fir_number`, `police_station`, `offences_charged`, `quashing_grounds`
- **Sections:** court_header, parties, synopsis_and_list_of_dates, facts, grounds_for_quashing, legal_provisions, precedents_relied_upon, prayer, verification
- **Key jurisprudence:** State of Haryana v. Bhajan Lal (1992) — 7 categories where quashing is warranted
- **Argument style:** CRAC (advocacy)

#### 3. Demand Notice — S.138 NI Act (`demand_notice_138`)

- **Statutory basis:** S.138 Negotiable Instruments Act, 1881
- **Required fields:** `drawer_name`, `drawer_address`, `cheque_number`, `cheque_date`, `cheque_amount`, `bank_name`, `return_date`, `return_reason`
- **Sections:** header, sender_details, recipient_details, reference, transaction_details, cheque_details, dishonour_details, demand, consequences, dispatch_clause, signature
- **Critical timeline:** Notice within 30 days of return memo, 15-day demand period
- **Argument style:** IRAC (factual/demand)

### Civil Litigation

#### 4. Plaint (`plaint`)

- **Statutory basis:** Order VII CPC
- **Required fields:** `plaintiff_details`, `defendant_details`, `cause_of_action`, `relief_sought`, `suit_valuation`
- **Sections:** court_header, parties, jurisdiction_and_valuation, facts_of_the_case, cause_of_action, limitation, legal_grounds, precedents_relied_upon, documents_relied_upon, prayer, verification
- **Key compliance:** Order VII Rule 11 (rejection grounds), S.80 CPC notice for government suits
- **Argument style:** IRAC (factual/neutral)

#### 5. Reply to Legal Notice (`reply_to_notice`)

- **Statutory basis:** Various
- **Required fields:** `original_notice_date`, `sender_name`, `sender_address`, `recipient_name`, `recipient_address`
- **Sections:** header, recipient_details, sender_details, reference, preliminary_objections, para_wise_reply, denial_of_claims, counter_claims, closing, signature
- **Key conventions:** "Without prejudice" protective language, specific denial framework
- **Argument style:** IRAC (defensive/factual)

### Supreme Court

#### 6. Special Leave Petition (`slp`)

- **Statutory basis:** Article 136, Constitution of India; SC Rules 2013
- **Required fields:** `impugned_order_details`, `lower_court_name`, `questions_of_law`
- **Sections:** synopsis, list_of_dates, questions_of_law, court_header, parties, impugned_order, facts, grounds_for_leave, precedents_relied_upon, prayer, verification
- **Key structure:** Synopsis + List of Dates come BEFORE the main petition (judges read this first)
- **Formatting:** SC profile mandatory — A4, TNR 14pt, 1.5 spacing, 4cm L/R margins
- **Argument style:** CRAC (advocacy — must establish substantial question of law)

### Family Law

#### 7. Divorce Petition (`divorce_petition`)

- **Statutory basis:** S.13 Hindu Marriage Act, 1955 / S.27 Special Marriage Act, 1954
- **Required fields:** `petitioner_details`, `respondent_details`, `marriage_date`, `marriage_place`, `grounds_for_divorce`
- **Sections:** court_header, parties, marriage_details, facts_of_the_case, grounds_for_divorce, legal_provisions, precedents_relied_upon, prayer, verification
- **Key grounds (S.13 HMA):** Cruelty, desertion (2+ years), conversion, unsoundness of mind, venereal disease, renunciation, presumption of death (7 years)
- **Argument style:** CRAC (advocacy)

#### 8. Maintenance Application (`maintenance_application`)

- **Statutory basis:** S.125 CrPC / S.144 BNSS / S.24 HMA
- **Required fields:** `applicant_details`, `respondent_details`, `relationship`, `income_details`
- **Sections:** court_header, parties, relationship_details, facts_of_the_case, income_and_means, grounds_for_maintenance, legal_provisions, precedents_relied_upon, prayer, verification
- **Key considerations:** Income disparity, standard of living, interim maintenance pending disposal
- **Argument style:** CRAC (advocacy)

### Commercial

#### 9. Consumer Complaint (`consumer_complaint`)

- **Statutory basis:** S.35 Consumer Protection Act, 2019
- **Required fields:** `complainant_details`, `opposite_party_details`, `product_or_service`, `deficiency_details`, `compensation_sought`
- **Sections:** court_header, parties, facts_of_the_case, deficiency_or_defect, loss_or_damage, legal_provisions, precedents_relied_upon, prayer, verification
- **Pecuniary jurisdiction:** District (up to Rs.1 Cr), State (Rs.1-10 Cr), National (above Rs.10 Cr)
- **Argument style:** IRAC (factual/claim-based)

### Cross-cutting

#### 10. General Affidavit (`affidavit`)

- **Statutory basis:** Various
- **Required fields:** `deponent_name`, `deponent_address`, `purpose`, `facts_to_state`
- **Sections:** deponent_identification, oath_clause, statement_of_facts, verification, notary_block
- **Key conventions:** "true to my knowledge" vs. "true to my information and belief" distinction per paragraph
- **Argument style:** IRAC (factual/sworn)

### Template Categories (for UI grouping)

| Category ID | Display Name | Templates |
|------------|-------------|-----------|
| `criminal` | Criminal Litigation | bail_application, anticipatory_bail, quashing_petition_482 |
| `civil` | Civil Litigation | plaint, written_statement, reply_to_notice, interim_application |
| `constitutional` | Constitutional / Supreme Court | writ_petition_226, writ_petition_32, slp, appeal |
| `family` | Family Law | divorce_petition, maintenance_application |
| `commercial` | Commercial | consumer_complaint, demand_notice_138 |
| `transactional` | Notices & General | legal_notice, affidavit |

---

## 5. Court Formatting Profiles

### CourtProfile Data Structure

```python
@dataclass(frozen=True)
class CourtProfile:
    court_id: str              # e.g. "supreme_court"
    display_name: str          # "Supreme Court of India"
    paper_size: str            # "A4" or "legal"
    font_name: str             # "Times New Roman"
    font_size_body: int        # 14 for SC, 12 for most HCs
    font_size_heading: int     # 16
    font_size_quote: int       # 12 for SC
    line_spacing: float        # 1.5 for SC
    margin_top_cm: float
    margin_bottom_cm: float
    margin_left_cm: float
    margin_right_cm: float
    header_format: str         # "IN THE HON'BLE SUPREME COURT OF INDIA"
    cover_color: dict[str, str]  # {"civil": "white", "criminal": "green"}
    requires_synopsis: bool
    requires_affidavit: bool
    numbering_style: str       # "arabic" or "roman"
    print_both_sides: bool
```

### 7 Profiles + Default

| Court | Paper | Body Font | Spacing | L/R Margins | Key Quirk |
|-------|-------|-----------|---------|-------------|-----------|
| `supreme_court` | A4 | TNR 14pt | 1.5 | 4cm / 4cm | Color-coded covers, synopsis mandatory, both-side printing |
| `delhi_hc` | A4 | TNR 14pt | Double (2.0) | 1.25in / 1.25in | E-filing max 300MB, filename max 45 chars |
| `bombay_hc` | Legal | TNR 12pt | 1.5 | 1.5in / 1in | Original Side has distinct rules |
| `madras_hc` | A4 | TNR 12pt | 1.5 | 1in / 1in | Tamil translation may be required |
| `karnataka_hc` | A4 | TNR 12pt | 1.5 | 1in / 1in | Kannada requirements for some filings |
| `calcutta_hc` | A4 | TNR 12pt | 1.5 | 1in / 1in | Distinct Original Side rules |
| `nclt` | A4 | TNR 12pt | 1.5 | 1in / 1in | Mandatory e-filing, DSC on every page, bookmarked PDFs |
| `default` | A4 | TNR 12pt | 1.5 | 1in / 1in | Fallback for unrecognized courts |

### Matching Logic

`target_court` is fuzzy-matched via alias dict:

```python
COURT_ALIASES: dict[str, str] = {
    "supreme court": "supreme_court",
    "sc": "supreme_court",
    "sci": "supreme_court",
    "delhi high court": "delhi_hc",
    "delhi hc": "delhi_hc",
    "dhc": "delhi_hc",
    "bombay high court": "bombay_hc",
    "bombay hc": "bombay_hc",
    "bhc": "bombay_hc",
    "madras high court": "madras_hc",
    "madras hc": "madras_hc",
    "mhc": "madras_hc",
    "karnataka high court": "karnataka_hc",
    "karnataka hc": "karnataka_hc",
    "khc": "karnataka_hc",
    "calcutta high court": "calcutta_hc",
    "calcutta hc": "calcutta_hc",
    "chc": "calcutta_hc",
    "nclt": "nclt",
    "nclat": "nclt",
    # ... more aliases
}
```

Lookup: `normalize(target_court) → alias dict → CourtProfile`. Unrecognized → `default` profile + warning in state.

### Flow Integration

1. `resolve_template_node` — looks up court profile, stores in `state["court_profile"]`
2. `draft_sections_node` — passes court-specific instructions (numbering style, synopsis requirement)
3. `assemble_document_node` — uses profile header format
4. `export_to_docx` / `export_to_pdf` — reads margins, fonts, spacing from profile

---

## 6. BNS/BNSS/BSA Integration

### Existing Infrastructure (Reused As-Is)

- `constants.py` — 567 bidirectional mappings (327 IPC→BNS, 153 CrPC→BNSS, 87 IEA→BSA)
- `amendment_service.py`:
  - `build_lookup_from_constants()` — sync fallback (no DB needed)
  - `get_amendment_lookups(db, redis)` — async DB-backed + Redis cached
  - `build_lookup()` — bidirectional `(act, section) → [sections]`
- Already used in research agent nodes (`common.py`) and search query expansion (`query.py`)

### New Wiring in Drafting Nodes

#### 6.1 `gather_provisions_node` — Dual-citation post-processing

After the LLM identifies statutory provisions, post-process each one:

```python
for provision in provisions:
    old_key = (provision["act"], provision["section"])
    new_sections = old_to_new.get(old_key, [])
    if new_sections:
        provision["new_code_section"] = new_sections[0]
        provision["new_code_act"] = {"IPC": "BNS", "CrPC": "BNSS", "IEA": "BSA"}.get(provision["act"], "")
```

This ensures every provision carries both old and new section numbers, regardless of what the LLM returned.

#### 6.2 `draft_sections_node` — Code context injection

Pass a filtered mapping context into each section's prompt:

```
Statute Code Context:
- Primary codes: BNS/BNSS/BSA (FIR date is after July 1, 2024)
- Cite new code as primary, old code in parentheses
- Relevant mappings:
  S.438 CrPC → S.482 BNSS (anticipatory bail)
  S.302 IPC → S.103 BNS (murder)
```

Filtered by: extract section numbers from `case_facts` using `extract_acts_cited()`, look up only those in amendment maps.

#### 6.3 `verify_final_node` — Cross-check

Scan assembled draft for section references. Flag any old-code citation without its new-code counterpart (and vice versa).

### Date Detection

```python
def determine_primary_code(case_facts: str, additional_context: dict) -> str:
    """Returns 'old' or 'new' based on FIR/filing date."""
    cutoff = date(2024, 7, 1)
    for key in ["fir_date", "filing_date", "offence_date"]:
        d = additional_context.get(key, "")
        parsed = try_parse_date(d)
        if parsed and parsed < cutoff:
            return "old"
    return "new"  # Default to new codes
```

Date fields are optional in `additional_context` — not part of `required_fields`.

---

## 7. Research-to-Draft Bridge

### Problem

Lawyer does research using Research Agent V3, gets memo with citations and statutes, then must manually re-enter everything when starting a draft.

### Solution: `/drafting/from-research` endpoint

```
POST /api/agents/drafting/from-research
{
    "research_execution_id": "uuid",
    "doc_type": "bail_application",
    "target_court": "supreme_court",
    "additional_context": {"accused_name": "...", "fir_number": "..."}
}
Returns: SSE stream (same as /drafting/run)
```

### Field Mapping

| Research State Field | → Drafting State Field | Transform |
|---------------------|----------------------|-----------|
| `grounding_citations` | `relevant_precedents` | Extract citation + title as PrecedentRef list |
| `statute_sections` | Injected into `gather_provisions` prompt | Pre-identified provisions |
| `query` | `case_facts` (pre-filled) | Direct copy |
| `arguments` | Injected into `draft_sections` prompt | Pre-researched grounds |

### Flow

1. Frontend: "Draft Document" button on research results page
2. User selects `doc_type`, `target_court`, fills required fields
3. Backend loads research `AgentExecution` record, extracts final state
4. Creates new drafting `AgentExecution` with pre-populated state
5. Graph runs normally — nodes see richer initial data but flow is identical
6. SSE stream returns as usual

### State Field

```python
research_context: dict  # Extracted from research session; empty if standalone
```

Nodes that see non-empty `research_context` incorporate it into prompts.

---

## 8. Differentiating Features (4)

### 8.1 Overruled Precedent Shield

**Problem:** Bombay HC fined Rs. 50,000 for AI-fabricated citations (Jan 2026). No tool systematically checks if cited precedents are still good law.

**Existing infrastructure:**
- `treatment.py` — `detect_treatment_in_text()`, `has_overruling_language()`, `classify_treatment_llm()`
- `common.py` — `detect_overruled_cases()`
- Neo4j `GraphStore.get_neighbors()` — find citing cases

**How it wires in:** Extend `verify_precedents_node`:
1. For each verified precedent, query Neo4j for cases that cite it
2. Run `has_overruling_language()` on neighboring case text
3. Tag each precedent: `treatment: "good_law" | "overruled" | "distinguished" | "doubted"`
4. `draft_sections_node` uses "good_law" confidently, skips "overruled" with warning, uses "distinguished" with caveat

**Est. change:** ~50 lines in `verify_precedents_node`

### 8.2 Citation Graph Suggestions

**Problem:** Lawyers may not know all relevant precedents. Flat keyword search misses structurally related cases.

**Existing infrastructure:**
- `common.py` — `get_citation_neighbors()` does parallel 2-hop neighbor fetch
- Neo4j citation graph with CITES relationships

**How it wires in:** New sub-step in `gather_provisions_node`:
1. Take verified precedents from user input
2. For each, call `get_neighbors(case_id, relationship="CITES", direction="both", depth=2)`
3. Filter neighbors: same legal topic, favorable outcome, not overruled
4. Present top 5 at `checkpoint_sources`: "These related cases were found via citation graph"
5. User can accept/reject at the HITL checkpoint

**Est. change:** ~60 lines in `gather_provisions_node`

### 8.3 Statutory Text Injection

**Problem:** When a draft cites "Section 438 CrPC", the judge must look up the actual text. No AI tool injects the section text.

**Existing infrastructure:**
- 2,932 statute sections in Pinecone (`vector_type: "statute"`)
- PostgreSQL has statute section metadata
- Research V3 `statute_lookup_node` already fetches statute text
- `extractor.py` — `extract_acts_cited()` identifies acts/sections in text

**How it wires in:** In `draft_sections_node`, for substantive sections:
1. After LLM generates draft text, extract statute references via `extract_acts_cited()`
2. Query Pinecone for `vector_type=statute` + matching act/section
3. Inject actual section text as indented quote block
4. Makes the document self-contained

**Est. change:** ~80 lines in `draft_sections_node`

### 8.4 Companion Affidavit Auto-Generation

**Problem:** Most court filings need a supporting affidavit. Lawyers draft it separately — tedious and repetitive.

**How it works:**
1. `DocumentTemplate` gains `requires_affidavit: bool` field
2. After `assemble_document_node`, if `requires_affidavit` is True:
   - Generate affidavit using same facts from main document
   - Standard structure: deponent ID, oath clause, statement of facts, verification, notary block
3. Stored in `state["affidavit_draft"]`
4. Export generates main document + affidavit (with page break) in single file

**Affidavit structure:**
```
1. Deponent identification (name, age, S/o or D/o, address, occupation)
2. "I, [name], do hereby solemnly affirm and state on oath as follows:"
3. Facts (numbered, mirroring main document paragraphs)
4. "The contents of paragraphs 1 to [N] are true to my knowledge and
    paragraphs [X] to [Y] are true to my information and belief."
5. Verification: "Verified at [Place] on this [date] day of [Month], [Year]..."
6. Deponent signature
7. "BEFORE ME" — Notary/Oath Commissioner block
```

**Templates requiring affidavit:** bail_application, anticipatory_bail, writ_petition_226, writ_petition_32, slp, appeal, quashing_petition_482, interim_application, divorce_petition, maintenance_application, consumer_complaint

**Est. change:** ~100 lines new code, 1 new prompt constant (`DRAFT_AFFIDAVIT_SYSTEM`)

---

## 9. CRAC vs IRAC Argument Style

### Problem

Current agent uses IRAC (Issue → Rule → Application → Conclusion) for all documents. CRAC (Conclusion → Rule → Application → Conclusion) is more persuasive for advocacy documents because it front-loads the answer.

### Solution

New field in `DocumentTemplate`:

```python
argument_style: str  # "irac" or "crac"
```

**IRAC templates (neutral/factual):** plaint, written_statement, legal_notice, reply_to_notice, demand_notice_138, affidavit, consumer_complaint

**CRAC templates (advocacy/persuasive):** bail_application, anticipatory_bail, writ_petition_226, writ_petition_32, slp, appeal, quashing_petition_482, interim_application, divorce_petition, maintenance_application

`draft_sections_node` reads `template["argument_style"]` and adjusts the per-section prompt:
- IRAC: "Structure using ISSUE, RULE, APPLICATION, CONCLUSION"
- CRAC: "Lead with your CONCLUSION, then support with RULE, APPLICATION, restate CONCLUSION"

---

## 10. State Schema Changes

### New Fields in DraftingState

```python
class DraftingState(TypedDict):
    # --- Existing (unchanged) ---
    doc_type: str
    case_facts: str
    language: str
    relevant_precedents: list[dict]
    additional_context: dict
    target_court: str
    template: dict
    statutory_provisions: list[dict]
    verified_precedents: list[dict]
    section_drafts: dict
    full_draft: str
    revision_feedback: str
    messages: Annotated[list[dict], operator.add]
    iteration: int
    error: str

    # --- New in V2 ---
    court_profile: dict            # Resolved CourtProfile as dict
    research_context: dict         # Extracted from research session (empty if standalone)
    affidavit_draft: str           # Auto-generated companion affidavit
    suggested_precedents: list[dict]  # Graph-suggested precedents shown at checkpoint
    primary_code: str              # "old" or "new" — determines IPC vs BNS as primary
```

### New Fields in DocumentTemplate

```python
@dataclass(frozen=True)
class DocumentTemplate:
    # --- Existing ---
    doc_type: str
    display_name: str
    sections: tuple[str, ...]
    required_fields: tuple[str, ...]
    statutory_basis: str
    court_header: str
    prompt_key: str
    # --- New in V2 ---
    category: str            # "criminal", "civil", "constitutional", "family", "commercial", "transactional"
    argument_style: str      # "irac" or "crac"
    requires_affidavit: bool # Whether to auto-generate companion affidavit
```

---

## 11. API Changes

### New Endpoints

#### `GET /api/agents/drafting/templates`

Returns grouped template list for frontend:

```json
{
    "categories": [
        {
            "id": "criminal",
            "display_name": "Criminal Litigation",
            "templates": [
                {
                    "doc_type": "bail_application",
                    "display_name": "Bail Application (S.439 CrPC)",
                    "required_fields": ["accused_name", "fir_number", "police_station", "offences_charged"],
                    "category": "criminal",
                    "requires_affidavit": true
                }
            ]
        }
    ]
}
```

#### `POST /api/agents/drafting/from-research`

```json
{
    "research_execution_id": "uuid",
    "doc_type": "bail_application",
    "target_court": "supreme_court",
    "additional_context": {"accused_name": "...", "fir_number": "..."}
}
```

Returns: SSE stream (identical format to `/drafting/run`).

### Modified Endpoints

#### `POST /api/agents/drafting/export/{execution_id}`

New optional field:

```json
{
    "format": "docx",
    "include_affidavit": true
}
```

### New SSE Event Fields

At `checkpoint_sources`:
```json
{
    "type": "checkpoint",
    "step": "sources",
    "data": {
        "verified_precedents": [...],
        "statutory_provisions": [...],
        "suggested_precedents": [...]
    }
}
```

At `checkpoint_draft`:
```json
{
    "type": "checkpoint",
    "step": "draft",
    "data": {
        "full_draft": "...",
        "section_drafts": {...},
        "affidavit_draft": "..."
    }
}
```

---

## 12. Export Engine Upgrades

### Profile-Driven Formatting

Both `export_to_docx` and `export_to_pdf` gain a `court_profile` parameter:

```python
async def export_to_docx(
    content: str,
    template: DocumentTemplate,
    *,
    title: str = "",
    court_profile: CourtProfile | None = None,
    affidavit: str = "",
) -> bytes:
```

Changes:
- Margins: read from `court_profile` (cm → Inches conversion)
- Body font size: from `court_profile.font_size_body`
- Heading font size: from `court_profile.font_size_heading`
- Line spacing: from `court_profile.line_spacing`
- Paper size: A4 vs Legal from `court_profile.paper_size`
- If `affidavit` non-empty: page break + affidavit as second section

Falls back to `default` profile if `court_profile` is None (backwards compatible).

### SC-Specific Export

For `supreme_court` profile:
- A4 (21cm × 29.7cm)
- 4cm left/right margins, 2cm top/bottom
- TNR 14pt body, 12pt for quotations/indents
- 1.5 line spacing
- Section breaks between Synopsis, main petition, and Affidavit

---

## 13. Prompt Architecture

### 10 New Prompt Constants

| Constant | Est. Lines | Key Content |
|----------|-----------|-------------|
| `DRAFT_ANTICIPATORY_BAIL_SYSTEM` | ~35 | Apprehension grounds, Sushila Aggarwal guidelines |
| `DRAFT_QUASHING_PETITION_SYSTEM` | ~40 | S.482 inherent powers, Bhajan Lal 7 categories |
| `DRAFT_DEMAND_NOTICE_138_SYSTEM` | ~30 | Strict S.138 timeline, cheque details, return memo |
| `DRAFT_PLAINT_SYSTEM` | ~45 | Cause of action, jurisdiction/valuation, Order VII compliance |
| `DRAFT_REPLY_TO_NOTICE_SYSTEM` | ~25 | Para-wise response, "without prejudice", denial framework |
| `DRAFT_SLP_SYSTEM` | ~50 | Synopsis + List of Dates, Questions of Law, Art.136 grounds |
| `DRAFT_DIVORCE_PETITION_SYSTEM` | ~35 | S.13 HMA grounds, marriage details, jurisdictional facts |
| `DRAFT_MAINTENANCE_APPLICATION_SYSTEM` | ~30 | S.125 CrPC / S.144 BNSS, income disparity |
| `DRAFT_CONSUMER_COMPLAINT_SYSTEM` | ~30 | CPA 2019 deficiency/defect definitions, pecuniary jurisdiction |
| `DRAFT_AFFIDAVIT_SYSTEM` | ~20 | Oath clause, knowledge vs. belief, verification format |

### Amendment Context Injection

Each prompt already says "Reference the IPC→BNS and CrPC→BNSS transition." V2 makes this deterministic by injecting actual mappings:

```
Statute Code Context:
- Primary: {primary_code} (based on FIR/filing date)
- Relevant mappings: [filtered from 567 total, only sections in case_facts]
```

Extracted via `extract_acts_cited()` from `extractor.py`, looked up in `build_lookup_from_constants()`.

---

## 14. File Changes Summary

### New Files (4)

| File | Purpose | Est. Lines |
|------|---------|-----------|
| `backend/app/core/drafting/court_profiles.py` | CourtProfile dataclass + 8 profiles + fuzzy matcher | ~200 |
| `backend/tests/unit/test_court_profiles.py` | Profile lookup, alias matching, fallback tests | ~80 |
| `backend/tests/unit/test_drafting_v2.py` | New templates, research bridge, affidavit, statute injection tests | ~300 |
| `docs/plans/2026-04-02-drafting-agent-v2-design.md` | This document | ~600 |

### Modified Files (8)

| File | Changes | Impact |
|------|---------|--------|
| `backend/app/core/drafting/templates.py` | +10 templates, +3 fields to DocumentTemplate | Medium |
| `backend/app/core/legal/prompts.py` | +11 prompt constants | Medium (additive) |
| `backend/app/core/agents/state.py` | +5 fields to DraftingState | Small |
| `backend/app/core/agents/nodes/drafting_nodes.py` | Wire amendment service, citation graph, statute injection, affidavit gen, CRAC | Large |
| `backend/app/core/drafting/export.py` | Profile-driven formatting, affidavit param | Medium |
| `backend/app/api/routes/agents.py` | +2 endpoints, modify export | Medium |
| `backend/app/core/agents/drafting.py` | Pass graph_store to closures | Small |
| `frontend/src/app/agents/drafting/page.tsx` | Category selector, affidavit preview, "Draft from Research" button | Medium |

### Unchanged Files

- `backend/app/core/agents/drafting.py` graph structure — no new nodes
- `backend/app/core/legal/constants.py` — 567 mappings sufficient
- `backend/app/core/legal/amendment_service.py` — used as-is
- `backend/app/core/legal/treatment.py` — used as-is
- `backend/app/core/agents/nodes/common.py` — existing helpers reused

### No New Dependencies

All required libraries (`python-docx`, `reportlab`, `langgraph`, `sqlalchemy`) already in project.

---

## 15. Testing Strategy

### Unit Tests (new file: `test_drafting_v2.py`)

- All 10 new templates resolve correctly
- Required field validation for each template
- Court profile lookup with aliases
- Court profile fallback to default
- Amendment mapping injection (old→new and new→old)
- Date detection logic (pre/post July 2024)
- CRAC vs IRAC prompt selection
- Affidavit generation for templates with `requires_affidavit=True`
- Research-to-draft field mapping
- Export with court profile formatting (margins, fonts)

### Existing Test Compatibility

- All existing V1 tests must pass unchanged (7 templates, current export format)
- New `DocumentTemplate` fields have defaults for backward compatibility:
  - `category: str = ""`
  - `argument_style: str = "irac"`
  - `requires_affidavit: bool = False`

---

## 16. Migration Notes

- No database migrations needed (amendment_maps table already exists)
- No Pinecone schema changes (statute vectors already ingested)
- No Neo4j schema changes (citation graph already built)
- Frontend changes are additive (new template selector, new buttons)
- Existing 7 templates gain `category`, `argument_style`, `requires_affidavit` fields with backward-compatible defaults
