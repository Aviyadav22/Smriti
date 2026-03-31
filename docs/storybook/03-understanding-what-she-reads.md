# Chapter 3: Understanding What She Reads

---

Reading text is one thing. *Understanding* it is another.

When Smriti reads a 50-page Supreme Court judgment, she needs to figure out:
- What's the case name?
- Who's the judge?
- What laws were discussed?
- What cases were cited?
- What did the court actually decide?

This is **metadata extraction** — and it's where AI and old-fashioned regex patterns work together like a tag team.

---

## The Two-Brain Approach

Avi could have gone all-in on AI: send the full judgment to Gemini, ask it to extract everything. But AI hallucinates. It might invent a citation that doesn't exist, or get a section number wrong.

He could have gone all-regex: pattern-match everything. But regex can't understand *meaning*. It can find "Section 302" but it can't figure out the *ratio decidendi* (the legal principle behind the decision).

**The solution: use both.**

```
LLM (Gemini)                    Regex
├── Creative extraction          ├── Deterministic validation
├── Understands context          ├── Never hallucinates
├── Can read messy text          ├── Fast and reliable
├── Extracts meaning             ├── Catches patterns LLM misses
└── Sometimes makes stuff up     └── Can't understand meaning
         ↓                                ↓
         └──────── MERGE & VALIDATE ──────┘
                         ↓
                  Final clean metadata
```

> **ADR-013**: LLM metadata extraction + regex validation (hybrid approach).

---

## What Gets Extracted (16 Fields)

For every judgment, Smriti extracts:

| Field | Example | Method |
|-------|---------|--------|
| **Title** | State of Maharashtra v. Rajesh Kumar | LLM + regex |
| **Citation** | (2024) 3 SCC 145 | LLM + regex patterns |
| **Court** | Supreme Court of India | LLM + validation |
| **Judge(s)** | D.Y. Chandrachud, J.B. Pardiwala | LLM + honorific stripping |
| **Year** | 2024 | LLM + range check [1800, current] |
| **Decision date** | 2024-03-15 | LLM + format validation |
| **Case type** | Criminal Appeal | LLM + 27 category mappings |
| **Case number** | Crl.A. No. 1234/2024 | LLM |
| **Petitioner** | State of Maharashtra | LLM |
| **Respondent** | Rajesh Kumar | LLM + cross-check (≠ petitioner) |
| **Acts cited** | IPC Section 302, 304 | LLM + regex (62+ acts recognized) |
| **Cases cited** | Bachan Singh v. State of Punjab | LLM + regex (15+ reporter formats) |
| **Ratio decidendi** | Death penalty requires "rarest of rare"... | LLM only (needs understanding) |
| **Keywords** | murder, death penalty, bail | LLM |
| **Disposal nature** | Allowed | LLM + validation |
| **Is reportable** | Yes | LLM |

---

## The LLM Step: Reading With Intelligence

The judgment text is sent to Gemini with a carefully crafted system prompt — 16 rules that tell the AI exactly what to do:

- "Extract the case title from the first page"
- "Look for the bench composition (judge names)"
- "Identify all acts and sections discussed, not just mentioned"
- "Extract the ratio decidendi — the core legal principle"
- "Return structured JSON matching this exact schema"

**The clever trick**: Judgments can be 100+ pages, but Gemini has a context limit. So Smriti sends the **head + tail** — the first 30,000 characters (where metadata lives) and the last 20,000 characters (where the order/judgment section usually is).

Why both? Because:
- **The beginning** has the case name, parties, bench, and case number
- **The end** has the disposal ("appeal allowed/dismissed"), the order, and often a summary

**Even cleverer**: When the original PDF is available, Smriti uses Gemini's **multimodal** capability — sending the actual PDF images to the AI so it can see the layout, headers, and formatting that get lost in text extraction.

---

## The Regex Step: Trust But Verify

After the LLM does its creative work, regex patterns validate and supplement the results.

### Citation Extraction (15+ Patterns)

Indian legal citations come in a dizzying variety of formats:

```
SCC:          (2020) 3 SCC 145
SCC Online:   2020 SCC OnLine SC 1234
AIR:          AIR 2020 SC 145
Neutral:      2023:INSC:1234  (post-2023 format)
SCR:          [2020] 3 SCR 145
CrLJ:         2020 CrLJ 3456
SCALE:        (2020) 3 SCALE 145
MANU:         MANU/SC/1234/2020
JT:           JT 2020 (3) SC 145
LiveLaw:      2020 LiveLaw (SC) 145
ITR:          [2020] 112 ITR 345
High Courts:  ILR, MLJ, KLT, BLR, GLR, ALJ, DLT...
```

Smriti has **16 compiled regex patterns** that catch all of these. Each pattern is carefully crafted to avoid false positives (you don't want "Section 302" to be mistaken for a citation to page 302).

### Act Recognition (62+ Acts)

When a judgment mentions laws, Smriti recognizes them:

```
"Indian Penal Code, 1860"        → IPC
"Bharatiya Nyaya Sanhita, 2023"  → BNS
"Code of Criminal Procedure"     → CrPC
"NDPS Act"                       → NDPS
"Prevention of Corruption Act"   → PCA
"Consumer Protection Act, 2019"  → CPA
... and 56 more
```

This normalization is critical. When a user searches for "IPC Section 302," they should find cases that mention "Section 302 of the Indian Penal Code, 1860" — they're the same thing.

### Judge Name Parsing

Indian judgments have wonderfully elaborate judge names:

```
"Hon'ble Mr. Justice Dr. D.Y. Chandrachud, Chief Justice of India"
```

Smriti strips all the honorifics to get clean names for filtering:

```
Input:  "Hon'ble Mr. Justice Dr. D.Y. Chandrachud"
Output: "D.Y. Chandrachud"
```

---

## The Merge: Three Sources of Truth

Smriti actually has three sources of metadata for each judgment:

1. **Parquet metadata** — from the AWS dataset (ground truth for basic fields like title, year)
2. **LLM extraction** — from Gemini (rich fields like ratio, keywords)
3. **Regex extraction** — pattern matching (citations, acts, section numbers)

The merge strategy:

```
For each field:
  1. If Parquet has it AND it passes validation → use Parquet (ground truth)
  2. If LLM has it AND it passes validation → use LLM (richer)
  3. If regex found additional values → supplement (add to the list)
  4. Track provenance: which source provided which field

Final output includes:
  metadata_provenance: {
    "title": "parquet",
    "citation": "llm",
    "acts_cited": "llm+regex",   ← regex found 3 more acts the LLM missed
    "cases_cited": "regex",       ← regex is better at citation patterns
    "ratio_decidendi": "llm"      ← only LLM can understand this
  }
```

---

## Cross-Field Validation

After merging, Smriti checks for logical consistency:

- **Petitioner ≠ Respondent** — they can't be the same person
- **Year matches decision date** — if the date says 2024, the year should be 2024
- **Disposal matches case type** — a "Criminal Appeal Allowed" makes sense; "Writ Petition Allowed" in a criminal matter doesn't
- **Acts cited match case type** — IPC in a civil suit is suspicious

If something fails validation, the confidence score drops and the field gets flagged.

---

## Confidence Scoring

Every extraction gets a confidence score from 0.0 to 1.0:

```
confidence = weighted_average(
    title:     present? + valid length?        (weight: HIGH)
    citation:  present? + valid format?        (weight: HIGH)
    court:     present? + recognized court?    (weight: HIGH)
    year:      present? + in valid range?      (weight: HIGH)
    judge:     present? + honorifics stripped?  (weight: HIGH)
    ratio:     present? + minimum length?      (weight: HIGH)
    acts:      present? + normalized?          (weight: MEDIUM)
    cases:     present? + valid format?        (weight: MEDIUM)
    keywords:  present?                        (weight: LOW)
    ...
)
```

A typical well-extracted judgment scores 0.85-0.95. Anything below 0.6 gets flagged for manual review.

---

## The Old-to-New Code Problem

In 2023, India replaced three foundational criminal laws:

| Old Code | New Code | Year |
|----------|----------|------|
| Indian Penal Code (IPC) | Bharatiya Nyaya Sanhita (BNS) | 2023 |
| Code of Criminal Procedure (CrPC) | Bharatiya Nagarik Suraksha Sanhita (BNSS) | 2023 |
| Indian Evidence Act (IEA) | Bharatiya Sakshya Adhiniyam (BSA) | 2023 |

This created a headache. A pre-2024 judgment cites "Section 302 IPC." A post-2024 judgment cites "Section 103 BNS." They're the same offense (murder). A search for either should find both.

**Smriti's solution: statute enrichment.** During metadata extraction:
- Pre-2024 cases: keep old code references, DON'T add new code (the judgment never mentioned BNS)
- Post-2024 cases: keep new code, AND add equivalent old code references (for backward compatibility)

This way, searching for "IPC 302" or "BNS 103" finds all murder cases, regardless of when they were decided.

---

> **Next: [Chapter 4 — The Memory Palace →](./04-the-memory-palace.md)**
>
> *Where text becomes numbers, and Smriti builds her long-term memory in a vector database.*

---

### In the Code

| What | Where |
|------|-------|
| LLM metadata extraction | [backend/app/core/ingestion/metadata.py](../../backend/app/core/ingestion/metadata.py) |
| Regex citation extraction | [backend/app/core/legal/extractor.py](../../backend/app/core/legal/extractor.py) |
| Statute enrichment (old↔new) | [backend/app/core/legal/statute_enrichment.py](../../backend/app/core/legal/statute_enrichment.py) |
| Metadata merge & validation | [backend/app/core/ingestion/pipeline.py](../../backend/app/core/ingestion/pipeline.py) |
| Extraction prompts | [docs/PROMPT_LIBRARY.md](../PROMPT_LIBRARY.md) — Section 1 |
| All 62+ act mappings | [backend/app/core/legal/extractor.py](../../backend/app/core/legal/extractor.py) → `ACT_PATTERNS` |
| Judge name parsing | [backend/app/core/ingestion/metadata.py](../../backend/app/core/ingestion/metadata.py) |
