# Chapter 6: The Web of Citations

---

Here's something that makes legal research fundamentally different from, say, searching the web.

When a court decides a case, it doesn't start from scratch. It builds on what previous courts have said. It *cites* earlier judgments — quoting them, following them, distinguishing them, or (dramatically) overruling them.

These citations create an invisible **web** — a network of connections between 35,000 cases. And this web is *incredibly* valuable.

---

## Why Citations Matter

If you find a case that supports your argument, the natural next question is:
- **Who else cited this case?** (Is it widely relied upon?)
- **Was it ever overruled?** (Is it still good law?)
- **Did any bench distinguish it?** (Are there exceptions?)
- **What's the most-cited case on this topic?** (What's the landmark judgment?)

These questions can't be answered by search alone. They require understanding the *relationships* between cases.

---

## Neo4j: The Graph Database

This is why Smriti uses Neo4j — a database designed specifically for relationships.

In Neo4j, the data looks like this:

```
[Bachan Singh v. State of Punjab (1980)]
         ↑ CITES
[Machhi Singh v. State of Punjab (1983)]
         ↑ CITES                    ↑ CITES
[Shankar Kisanrao v. State (2023)]  [Ravji v. State of Rajasthan (1996)]
                                              ↑ OVERRULES
                                    [Machhi Singh v. State (1983)]
```

Each **node** is a case (with id, title, citation, court, year).
Each **edge** is a citation relationship (CITES, OVERRULES, DISTINGUISHES, APPLIES_PRINCIPLE).

> **ADR-006**: Neo4j AuraDB for native graph queries and citation traversal.

---

## Building the Graph

During ingestion (Chapter 2-4), after extracting citations from a judgment, Smriti:

1. **Creates a Case node** for the current judgment (MERGE — idempotent, won't duplicate)
2. **Finds or creates nodes** for each cited case
3. **Creates CITES edges** between them
4. **Detects citation strength**:

| Strength | Meaning | How Detected |
|----------|---------|-------------|
| **BINDING** | Must be followed | Same court or higher court |
| **PERSUASIVE** | Can be considered | Different court, older judgment |
| **DISTINGUISHABLE** | Similar but different facts | Language like "the facts differ" |
| **OVERRULED** | No longer good law | Language like "overruled," "no longer good law" |

The treatment detection uses NLP to understand *how* a case is being cited:

```python
detect_treatment_in_text(text, case_name) → "followed" | "applied" | "distinguished" | "overruled"
```

---

## Citation Communities

Here's one of the most interesting features.

Using graph algorithms (NetworkX), Smriti detects **citation communities** — clusters of cases that heavily cite each other. These communities often correspond to legal topics:

```
Community 1: "Bail under NDPS Act"
├── Union of India v. Ram Samujh (1999)
├── Narcotics Control Bureau v. Kishan Lal (1991)
├── Tofan Singh v. State of Tamil Nadu (2020)
└── ... 12 more cases

Community 2: "Right to Privacy"
├── K.S. Puttaswamy v. Union of India (2017)
├── R. Rajagopal v. State of Tamil Nadu (1994)
└── ... 8 more cases
```

These communities are embedded as vectors (the `community` vector type from Chapter 4) and are used by the research agent to find entire clusters of related precedent.

---

## What You Can Do With the Graph

### 1. Citation Trail
"Show me every case that cited Maneka Gandhi v. Union of India"
→ Neo4j traverses all incoming CITES edges → returns the chain

### 2. Authority Score
"How authoritative is this judgment?"
→ Count incoming citations (cited_by_count) → more citations = more authority

### 3. Overruling Detection
"Is this case still good law?"
→ Check if any later case has an OVERRULES edge pointing to it

### 4. Bench Composition Analysis
"How do cases decided by 5-judge benches compare to 2-judge benches?"
→ Filter by bench_type, compare citation patterns

### 5. Temporal Analysis
"How has the interpretation of Section 498A evolved?"
→ Trace citations chronologically → see how the law changed over time

---

## Citation Equivalents

Indian legal citations come in many formats. The same case might be cited as:

```
(2020) 3 SCC 145
2020 SCC OnLine SC 1234
AIR 2020 SC 145
2020:INSC:1234
MANU/SC/1234/2020
```

All five are the *same case*. Smriti maintains a `case_citation_equivalents` table that maps between these formats. When building the graph, if two citations resolve to the same case, they create a single node — not five disconnected ones.

---

## Precedent Strength

Beyond simple citations, Smriti classifies the *strength* of precedent:

```python
classify_precedent_strength(citing_case, cited_case):
    if same_court and cited_is_larger_bench:
        return BINDING
    if higher_court:
        return BINDING
    if same_court and same_bench_size:
        return PERSUASIVE
    if overruling_language_detected:
        return OVERRULED
    if distinguishing_language_detected:
        return DISTINGUISHABLE
```

This matters enormously for lawyers. A binding precedent from a 5-judge Constitution Bench carries far more weight than a persuasive observation from a 2-judge Division Bench.

---

> **Next: [Chapter 7 — The Research Agent →](./07-the-research-agent.md)**
>
> *Where Smriti stops being a search engine and starts being a research assistant — thinking, planning, and writing like a lawyer.*

---

### In the Code

| What | Where |
|------|-------|
| Graph building | [backend/app/core/ingestion/pipeline.py](../../backend/app/core/ingestion/pipeline.py) → `_build_citation_graph()` |
| Neo4j provider | `backend/app/core/providers/graph/neo4j_store.py` |
| Treatment detection | `backend/app/core/legal/treatment.py` |
| Precedent strength | `backend/app/core/legal/precedent_strength.py` |
| Citation equivalents | `backend/app/models/` → `case_citation_equivalents` |
| Graph API routes | `backend/app/api/routes/graph.py` |
| Community detection | Graph workers in research agent |
