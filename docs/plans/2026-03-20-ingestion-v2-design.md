# Ingestion Pipeline V2 — Future-Proofing Design

> **Date**: 2026-03-20 | **Status**: Approved
> **Goal**: Extract maximum data during ingestion to support future features (Strategy Simulation, Judge Analytics V2, Precedent Intelligence, Document Generation) without re-processing 35K+ judgments.

---

## 1. APPROACH: TWO-PASS ARCHITECTURE

### Pass 1: "Ingest Everything" (Flash, ~₹24K for 35K SC cases)
- Extract all 22 new fields using Gemini 2.5 Flash with full judgment text
- Store in PostgreSQL, Pinecone metadata, Neo4j
- Mark each case with `enrichment_status: "flash_only"`

### Pass 2: "Enrich on Demand" (Pro, pay-as-you-go)
- Background script or on-demand CLI
- Re-extracts 8 complex reasoning fields using Gemini 2.5 Pro
- Targets: `arguments_raised`, `citation_treatments`, `judicial_tone`, `legal_principles_applied`, `procedural_history`, `issue_classification`, `fact_pattern_tags`, `operative_order`
- Cost: ~₹2.4 per case, so enriching 1,000 targeted cases = ₹2,400
- Updates PostgreSQL + Neo4j edges, marks as `enrichment_status: "pro_enriched"`

### Cost Summary

| Model | Per-judgment | 35K judgments | INR |
|---|---|---|---|
| Flash (Pass 1) | ~₹0.68 | ₹24,000 | Full extraction |
| Pro (Pass 2, per case) | ~₹6.80 | ₹2,38,850 (if all) | Selective enrichment |
| Hybrid recommendation | — | ~₹89,000 | Flash + Pro for 8 fields |

---

## 2. NEW FIELDS (22 total)

### Group A: Judge Behavior Modeling

| # | Field | Type | Source | Purpose |
|---|---|---|---|---|
| 1 | `arguments_raised` | `JSONB` | LLM | `[{party, argument_type, argument_summary, statutory_basis, accepted}]` — which argument types succeed before which judges |
| 2 | `relief_granted` | `TEXT` | LLM | What specific relief was granted. Delta with relief_sought = judge leniency |
| 3 | `relief_sought` | `TEXT` | LLM | What petitioner asked for |
| 4 | `sentence_details` | `JSONB` | LLM | Criminal: `{offense, sentence_type, quantum, fine_amount, conditions}` |
| 5 | `damages_awarded` | `JSONB` | LLM | Civil: `{amount, currency, type}` — compensatory/punitive/nominal/costs |
| 6 | `judicial_tone` | `VARCHAR(30)` | LLM | `neutral/stern/sympathetic/critical/academic/reformist` — judge persona modeling |
| 7 | `key_observations` | `TEXT[]` | LLM | Obiter dicta (max 5). Reveals judicial philosophy |
| 8 | `hearing_count` | `INTEGER` | LLM | Number of hearings mentioned. Proxy for complexity |

### Group B: Citation Intelligence

| # | Field | Type | Source | Purpose |
|---|---|---|---|---|
| 9 | `citation_treatments` | `JSONB` | LLM | `[{cited_case, treatment, context, paragraph}]` — HOW each case was used |
| 10 | `distinguished_cases` | `TEXT[]` | LLM | Cases explicitly distinguished |
| 11 | `overruled_cases` | `TEXT[]` | LLM | Cases explicitly overruled (more reliable than regex) |
| 12 | `legal_principles_applied` | `TEXT[]` | LLM | Named doctrines (e.g., "doctrine of proportionality") |

### Group C: Procedural Intelligence

| # | Field | Type | Source | Purpose |
|---|---|---|---|---|
| 13 | `procedural_history` | `JSONB` | LLM | `[{court, case_number, date, outcome, judge}]` — chain from trial → HC → SC |
| 14 | `interim_orders` | `TEXT[]` | LLM | Stay orders, interim relief during pendency |
| 15 | `filing_date` | `DATE` | LLM/Parquet | When filed (delta with decision_date = case duration) |
| 16 | `urgency_indicators` | `TEXT[]` | LLM | "urgent hearing", "suo motu", "expedited" mentions |

### Group D: Party & Case Intelligence

| # | Field | Type | Source | Purpose |
|---|---|---|---|---|
| 17 | `party_counsel` | `JSONB` | LLM | `[{party, counsel_name, designation}]` — enables counsel profiling |
| 18 | `issue_classification` | `TEXT[]` | LLM | Hierarchical tags (e.g., "fundamental_rights.article_21.right_to_life") |
| 19 | `fact_pattern_tags` | `TEXT[]` | LLM | Factual patterns (e.g., "land_dispute", "dowry_death") |

### Group E: Output Quality

| # | Field | Type | Source | Purpose |
|---|---|---|---|---|
| 20 | `operative_order` | `TEXT` | LLM | Verbatim text of court's order. Lawyers need this for drafting |
| 21 | `conditions_imposed` | `TEXT[]` | LLM | Conditions attached to relief (bail conditions, compliance timelines) |
| 22 | `costs_awarded` | `JSONB` | LLM | `{amount, to_whom, reason}` |

### Enrichment Tracking

| Field | Type | Purpose |
|---|---|---|
| `enrichment_status` | `VARCHAR(20)` | `flash_only / pro_enriched / failed` |

---

## 3. PDF DEEP-LINKING & PAGE MAPPING

### Problem
Footnotes should link to the exact page in the PDF where the cited text appears.

### Solution: Page Map

During existing `extract_pdf_text()`, track page boundaries (zero LLM cost):

```python
class PageMap(TypedDict):
    page_number: int   # 1-indexed
    char_start: int    # Character offset in full_text
    char_end: int      # Character offset end
```

### New Storage

| Store | Field | Notes |
|---|---|---|
| PostgreSQL | `page_map JSONB` | ~2KB per case, ~70MB for 35K cases |
| Pinecone | `page_start`, `page_end`, `char_start`, `char_end` per chunk | Enables "go to exact page" from search results |

### Deep-Link Flow

```
Footnote click → chunk has para_start/para_end → lookup char offset in full_text
  → page_map lookup → char offset maps to page N → open PDF at page N
```

### PDF Serving

Add `GET /api/v1/cases/{id}/pdf` endpoint returning signed GCS URL (prod) or file stream (dev).

---

## 4. STORAGE SCHEMA CHANGES

### 4.1 PostgreSQL Migration 021

```sql
-- Group A: Judge Behavior Modeling
ALTER TABLE cases ADD COLUMN arguments_raised JSONB;
ALTER TABLE cases ADD COLUMN relief_granted TEXT;
ALTER TABLE cases ADD COLUMN relief_sought TEXT;
ALTER TABLE cases ADD COLUMN sentence_details JSONB;
ALTER TABLE cases ADD COLUMN damages_awarded JSONB;
ALTER TABLE cases ADD COLUMN judicial_tone VARCHAR(30);
ALTER TABLE cases ADD COLUMN key_observations TEXT[];
ALTER TABLE cases ADD COLUMN hearing_count INTEGER;

-- Group B: Citation Intelligence
ALTER TABLE cases ADD COLUMN citation_treatments JSONB;
ALTER TABLE cases ADD COLUMN distinguished_cases TEXT[];
ALTER TABLE cases ADD COLUMN overruled_cases TEXT[];
ALTER TABLE cases ADD COLUMN legal_principles_applied TEXT[];

-- Group C: Procedural Intelligence
ALTER TABLE cases ADD COLUMN procedural_history JSONB;
ALTER TABLE cases ADD COLUMN interim_orders TEXT[];
ALTER TABLE cases ADD COLUMN filing_date DATE;
ALTER TABLE cases ADD COLUMN urgency_indicators TEXT[];

-- Group D: Party & Case Intelligence
ALTER TABLE cases ADD COLUMN party_counsel JSONB;
ALTER TABLE cases ADD COLUMN issue_classification TEXT[];
ALTER TABLE cases ADD COLUMN fact_pattern_tags TEXT[];

-- Group E: Output Quality
ALTER TABLE cases ADD COLUMN operative_order TEXT;
ALTER TABLE cases ADD COLUMN conditions_imposed TEXT[];
ALTER TABLE cases ADD COLUMN costs_awarded JSONB;

-- PDF Deep-Linking
ALTER TABLE cases ADD COLUMN page_map JSONB;

-- Enrichment Tracking
ALTER TABLE cases ADD COLUMN enrichment_status VARCHAR(20) DEFAULT 'flash_only';

-- Indexes
CREATE INDEX ix_cases_judicial_tone ON cases (judicial_tone);
CREATE INDEX ix_cases_filing_date ON cases (filing_date);
CREATE INDEX ix_cases_fact_pattern_tags ON cases USING GIN (fact_pattern_tags);
CREATE INDEX ix_cases_issue_classification ON cases USING GIN (issue_classification);
CREATE INDEX ix_cases_legal_principles ON cases USING GIN (legal_principles_applied);
CREATE INDEX ix_cases_distinguished ON cases USING GIN (distinguished_cases);
CREATE INDEX ix_cases_overruled ON cases USING GIN (overruled_cases);
CREATE INDEX ix_cases_party_counsel ON cases USING GIN (party_counsel jsonb_path_ops);
CREATE INDEX ix_cases_enrichment_status ON cases (enrichment_status);
```

### 4.2 Pinecone Metadata (per chunk)

Add to existing metadata:

```python
"judicial_tone":       str,        # For tone-filtered search
"fact_pattern_tags":   list[str],  # Max 5, for pattern-based retrieval
"issue_classification": list[str], # Max 5, for issue-based filtering
"page_start":          int,        # PDF page number (1-indexed)
"page_end":            int,        # PDF page number end
"char_start":          int,        # Character offset in full_text
"char_end":            int,        # Character offset end
```

### 4.3 Neo4j — New Nodes & Enhanced Edges

```cypher
-- Enhanced CITES edges (richer treatment data)
MATCH (a:Case {id: $case_id}), (b:Case {citation: $cited_citation})
MERGE (a)-[r:CITES]->(b)
SET r.treatment = $treatment,
    r.context = $context,          -- NEW: "distinguished on facts"
    r.paragraph = $paragraph       -- NEW: paragraph number

-- New: Counsel nodes + REPRESENTED_BY edges
CREATE CONSTRAINT counsel_name_unique IF NOT EXISTS
FOR (c:Counsel) REQUIRE c.name IS UNIQUE;

MERGE (c:Counsel {name: $counsel_name})
SET c.designation = $designation
MERGE (case:Case {id: $case_id})-[:REPRESENTED_BY {party: $party}]->(c)

-- New: LegalPrinciple nodes
CREATE CONSTRAINT principle_name_unique IF NOT EXISTS
FOR (p:LegalPrinciple) REQUIRE p.name IS UNIQUE;

MERGE (p:LegalPrinciple {name: $principle_name})
MERGE (case:Case {id: $case_id})-[:APPLIES_PRINCIPLE]->(p)

-- New: Issue nodes
CREATE CONSTRAINT issue_tag_unique IF NOT EXISTS
FOR (i:Issue) REQUIRE i.tag IS UNIQUE;

MERGE (i:Issue {tag: $issue_tag})
MERGE (case:Case {id: $case_id})-[:ADDRESSES]->(i)
```

### 4.4 Updated FTS Trigger

Add to searchable_text weights:
- **C weight**: + `operative_order`
- **D weight**: + `legal_principles_applied[]`, `issue_classification[]`

---

## 5. LLM PROMPT CHANGES

### New Extraction Rules (add to existing 16-rule system prompt)

```
17. ARGUMENTS: Extract each distinct legal argument raised by each party.
    Classify argument_type: constitutional | statutory_interpretation | procedural |
    factual | precedent_based | policy | equity | jurisdictional | limitation | evidence.
    Mark accepted=true if upheld, false if rejected, null if unclear.

18. RELIEF: Extract relief_sought and relief_granted separately. For criminal cases,
    extract sentence_details {offense, sentence_type, quantum, fine_amount, conditions}.
    For civil monetary awards, extract damages_awarded {amount, currency, type}.

19. OPERATIVE ORDER: Extract the exact operative portion verbatim (usually starts with
    "In view of the above" or "The appeal is hereby"). Do not summarize.

20. CITATION TREATMENTS: For each cited case, identify treatment: followed | applied |
    referred_to | distinguished | overruled | approved | doubted | explained | not_followed.
    Include 1-2 sentence context of HOW it was used.

21. COUNSEL: Extract advocate names per party. Identify Senior Advocates ("Sr. Adv."),
    AG/SG/ASG, Amicus Curiae, Advocate-on-Record. Use designation enum:
    senior_advocate | advocate | aag | ag | sg | asg | amicus | advocate_on_record.

22. JUDICIAL TONE: Classify overall tone: neutral (standard), stern (harsh/admonishments),
    sympathetic (concern for parties), critical (criticism of lower courts/government),
    academic (extensive doctrinal analysis), reformist (policy/law reform suggestions).

23. LEGAL PRINCIPLES: Extract named legal doctrines applied (e.g., "doctrine of basic
    structure", "Wednesbury unreasonableness", "last seen doctrine").

24. FACT PATTERNS: Tag 1-5 factual pattern categories: land_dispute, dowry_death,
    corporate_fraud, bail_application, service_matter, environmental_clearance,
    police_encounter, property_partition, contract_breach, tax_evasion,
    election_dispute, labor_dispute, motor_accident, medical_negligence,
    defamation, contempt, public_interest, arbitration, insurance_claim, etc.
```

### Context Strategy Change

**Before**: head(20K) + middle(15K) + tail(15K) = 50K chars truncated
**After**: Send full judgment text (Gemini 1M context). Average SC judgment = ~60K chars = ~20K tokens. Well within limits.

---

## 6. FILES TO MODIFY

| File | Change | Effort |
|---|---|---|
| `backend/app/core/ingestion/metadata.py` | Add 22 fields to CaseMetadata, update schema, send full text | Medium |
| `backend/app/core/ingestion/pdf.py` | Track page boundaries → return page_map | Small |
| `backend/app/core/ingestion/pipeline.py` | Update _insert_case() for new columns, update Pinecone metadata, update Neo4j graph building for new edges/nodes | Medium |
| `backend/app/core/legal/prompts.py` | Add rules 17-24, extend extraction schema | Medium |
| `backend/app/models/case.py` | Add 23 new columns (22 fields + page_map) | Small |
| `backend/migrations/versions/021_*.py` | New migration | Small |
| `backend/scripts/enrich_pro.py` | **NEW** — Pass 2 enrichment script | Medium |
| `backend/app/api/routes/cases.py` | Add PDF serving endpoint | Small |

### What Does NOT Change
- `pdf.py` extraction logic (unchanged, just add offset tracking)
- `chunker.py` (unchanged)
- Embedding logic (same chunks, richer metadata)
- `anonymizer.py` (unchanged)
- `rate_limiter.py` (unchanged)
- `ingest_s3.py` CLI interface (unchanged — it calls pipeline.ingest_judgment())

---

## 7. FUTURE FEATURES ENABLED

| Feature | Fields It Uses |
|---|---|
| **Strategy Simulation** | arguments_raised, relief_sought/granted, judicial_tone, citation_treatments, fact_pattern_tags, issue_classification |
| **Judge Analytics V2** | judicial_tone, arguments_raised (accepted/rejected by judge), sentence_details, damages_awarded, hearing_count, key_observations |
| **Judge Persona Modeling** | judicial_tone, key_observations, legal_principles_applied, citation_treatments |
| **Opposing Counsel Profiling** | party_counsel, arguments_raised (which counsel's arguments succeed) |
| **Forum Selection Advisor** | procedural_history, fact_pattern_tags, filing_date, urgency_indicators |
| **Case Timeline Generator** | procedural_history, filing_date, interim_orders |
| **Precedent Strength V2** | citation_treatments, distinguished_cases, overruled_cases, legal_principles_applied |
| **Document Generation** | operative_order, conditions_imposed, relief_granted, costs_awarded |
| **PDF Deep-Linking** | page_map, per-chunk page_start/page_end/char_start/char_end |
| **Research Agent V2** | All fields — richer Pinecone metadata enables better filtering |

---

## 8. ARGUMENT TYPE TAXONOMY

Standardized `argument_type` enum for `arguments_raised`:

| Type | Description | Example |
|---|---|---|
| `constitutional` | Fundamental rights, constitutional provisions | "Violation of Article 21" |
| `statutory_interpretation` | Interpreting specific sections of a statute | "Section 302 IPC requires premeditation" |
| `procedural` | Procedural rights, limitation, jurisdiction | "Appeal is time-barred under Section 5" |
| `factual` | Dispute on facts, evidence assessment | "Prosecution failed to prove motive" |
| `precedent_based` | Relying on prior decisions | "Following ratio in Bachan Singh" |
| `policy` | Public policy, societal impact | "Death penalty should be restricted" |
| `equity` | Fairness, natural justice | "Principles of natural justice violated" |
| `jurisdictional` | Court's authority to hear the case | "This court lacks territorial jurisdiction" |
| `limitation` | Time-bar arguments | "Application filed beyond 30-day window" |
| `evidence` | Admissibility, weight of evidence | "Confession under Section 25 is inadmissible" |

---

## 9. FACT PATTERN TAXONOMY

Standardized tags for `fact_pattern_tags`:

`land_dispute`, `dowry_death`, `corporate_fraud`, `bail_application`, `service_matter`,
`environmental_clearance`, `police_encounter`, `property_partition`, `contract_breach`,
`tax_evasion`, `election_dispute`, `labor_dispute`, `motor_accident`, `medical_negligence`,
`defamation`, `contempt`, `public_interest`, `arbitration`, `insurance_claim`,
`family_dispute`, `custody_battle`, `sexual_offense`, `narcotics`, `terrorism`,
`cybercrime`, `intellectual_property`, `banking_finance`, `real_estate`, `education`,
`consumer_protection`, `corruption`, `extradition`, `habeas_corpus`, `writ_petition`,
`review_petition`, `curative_petition`, `special_leave_petition`, `transfer_petition`,
`compensation_claim`, `civil_appeal`, `criminal_appeal`
