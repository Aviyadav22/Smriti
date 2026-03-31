# Chapter 5: The Art of Finding

---

Smriti can now read documents, understand them, and remember them. But the whole point is to *find* the right ones when someone asks a question.

This is the search pipeline — and it's where everything comes together.

---

## The Three Search Engines Inside Smriti

Smriti doesn't rely on one search method. She uses **three**, then combines the results:

### 1. Full-Text Search (PostgreSQL)

Good old keyword search — but smarter than you'd expect.

PostgreSQL has a built-in feature called `tsvector` that creates searchable indexes of text. When you search for "bail under NDPS Act," it:
- Stems words: "bail" → "bail", "conditions" → "condit"
- Handles phrases: "rarest of rare" matches as a phrase
- Supports boolean: "murder AND bail" or "murder OR homicide"
- Ranks by proximity: cases where "bail" and "NDPS" appear near each other rank higher

Smriti uses `websearch_to_tsquery` — the most powerful query parser PostgreSQL offers, supporting phrases wrapped in quotes and boolean operators.

The ranking function is `ts_rank_cd` (cover density), which rewards documents where search terms appear close together. This is much better for legal text than simple frequency counting.

> **ADR-019**: FTS ranking uses ts_rank_cd for proximity-aware legal phrase ranking.

### 2. Semantic Search (Pinecone)

This is the embedding-powered search from Chapter 4. The user's query gets embedded using `RETRIEVAL_QUERY` task type, then compared against all stored vectors.

The magic: "What is the punishment for murder?" matches "Section 302 prescribes the death penalty or life imprisonment for culpable homicide amounting to murder" — even though they share almost no keywords.

Pinecone also supports **metadata filters**: court, year range, case type, vector type. So you can search for meaning *within* constraints.

### 3. Exact Citation Lookup

If the user types something that looks like a citation — "(2024) 3 SCC 145" or "2023:INSC:1234" — Smriti recognizes it and does a direct database lookup instead of (or in addition to) semantic search.

---

## Combining Results: Reciprocal Rank Fusion

Three search engines means three ranked lists of results. How do you combine them?

**Reciprocal Rank Fusion (RRF)** with k=60.

The formula is simple but powerful:

```
RRF_score = Σ (1 / (60 + rank))

For each document:
  - If it's rank 1 in vector search: score += 1/61 = 0.0164
  - If it's rank 5 in FTS: score += 1/65 = 0.0154
  - If it's not in citation search: score += 0

Total RRF score = 0.0164 + 0.0154 = 0.0318
```

Why k=60? It's a well-studied constant that balances the influence of high-ranked and lower-ranked results. Too small (k=1), and only the top result matters. Too large (k=1000), and all ranks feel the same.

Why RRF instead of weighted averages? Because the *scores* from different search engines aren't comparable. A Pinecone cosine similarity of 0.85 and a PostgreSQL ts_rank of 3.2 mean completely different things. RRF only cares about *rank*, not score — it's score-agnostic.

> **ADR-009**: RRF (k=60) for score-agnostic merging of multiple search sources.

---

## The Reranker: The Final Judge

After RRF combines the results, the top 100 go through one more filter: **Cohere's rerank-v4.0-pro**.

The reranker is a specialized AI model that reads each result *in context of the query* and gives it a relevance score. It's much more expensive than embedding search, which is why we only run it on the top 100 (not all 35,000 cases).

Think of it as a second opinion:
- Vector search says "this chunk is semantically similar to the query"
- The reranker says "yes, but is it actually *relevant* and *useful* for answering this specific question?"

The reranker catches false positives that embedding similarity misses — like a chunk that uses similar legal language but is actually about a completely different issue.

> **ADR-008**: Cohere rerank-v4.0-pro for best-in-class relevance scoring.

---

## Query Understanding: Before the Search Even Starts

Before running any search, Smriti asks Gemini to *understand* the query:

```
User types: "Can a person get bail in NDPS cases?"

Gemini analyzes:
{
  "topic": "bail jurisprudence under NDPS Act",
  "jurisdiction": "Supreme Court",
  "key_entities": ["bail", "NDPS Act", "Section 37"],
  "inferred_filters": {
    "act": "NDPS",
    "court": "Supreme Court"
  },
  "query_intent": "law_research",
  "complexity": "medium",
  "explanation": "Searching for Supreme Court precedents on bail
                  under the Narcotic Drugs and Psychotropic
                  Substances Act, particularly Section 37 which
                  imposes special bail restrictions."
}
```

This understanding helps in two ways:
1. **Better search**: Smriti can add inferred filters and rewrite the query for better matching
2. **User experience**: The "explanation" is shown to the user, confirming what Smriti understood

---

## The Full Search Flow

```
User query: "bail conditions for economic offenses"
        ↓
[1] QUERY UNDERSTANDING (Gemini)
    → topic: "bail in economic offenses"
    → entities: ["bail", "economic offense", "prevention of money laundering"]
    → intent: law_research
        ↓
[2] PARALLEL SEARCH
    ┌─ Vector (Pinecone): embed query → find similar chunks
    ├─ FTS (PostgreSQL): websearch_to_tsquery → keyword match
    └─ Citation (if applicable): direct lookup
        ↓
[3] RRF FUSION (k=60)
    → Combine 3 ranked lists into 1
    → Deduplicate (same case from different sources)
    → Top 100
        ↓
[4] RERANKING (Cohere)
    → Score each result in context of the query
    → Re-sort by relevance
        ↓
[5] POST-PROCESSING
    → Add ratio decidendi (up to 3,000 chars per result)
    → Format: case_id, title, citation, court, year, snippet, score
    → Paginate (default 10, max 50)
        ↓
[6] RESPONSE
    {
      "query_understanding": { topic, entities, explanation },
      "results": [ ... top 10 ... ],
      "total_count": 847,
      "facets": {
        "courts": [{"Supreme Court": 600}, {"Delhi HC": 100}, ...],
        "years": [{"2024": 45}, {"2023": 78}, ...],
        "case_types": [{"Criminal Appeal": 200}, ...]
      },
      "execution_time_ms": 1240
    }
```

---

## Filters: Narrowing the Haystack

Users can filter search results by:

| Filter | Example | How It Works |
|--------|---------|-------------|
| **Court** | Supreme Court, Delhi HC | Metadata filter on Pinecone + WHERE clause in PG |
| **Year range** | 2020-2024 | Metadata filter + WHERE clause |
| **Case type** | Criminal Appeal | 27 normalized categories |
| **Bench type** | Division bench | Single, division, full, constitutional |
| **Judge** | D.Y. Chandrachud | Array GIN index search |
| **Act** | NDPS Act | Normalized to short codes (IPC, NDPS, etc.) |
| **Section** | Section 302 | Combined with act filter |

Filters are applied *before* the search runs — not after. This means Pinecone only searches within matching documents, making results both faster and more relevant.

---

## Hindi Support

Smriti supports search in Hindi (and will add more languages). When a user searches in Hindi:

1. **Detect language** — is this Hindi or English?
2. **Translate query** — Hindi → English (using Gemini)
3. **Search** — run the English query through the normal pipeline
4. **Translate results** — English snippets → Hindi
5. **Return** — both English and Hindi versions

This is a pragmatic choice. The judgments are in English, so search works best in English. But Indian lawyers should be able to search in their language.

---

> **Next: [Chapter 6 — The Web of Citations →](./06-the-web-of-citations.md)**
>
> *Where Smriti maps the invisible web connecting 35,000 cases to each other.*

---

### In the Code

| What | Where |
|------|-------|
| Hybrid search engine | `backend/app/core/search/hybrid.py` |
| Query understanding | `backend/app/core/search/query.py` |
| RRF fusion | `backend/app/core/search/hybrid.py` → RRF merge |
| Search API route | [backend/app/api/routes/search.py](../../backend/app/api/routes/search.py) |
| Search filters | `backend/app/core/search/query.py` → `SearchFilters` |
| Reranker interface | `backend/app/core/interfaces/reranker.py` |
| Cohere reranker | `backend/app/core/providers/reranker/cohere_reranker.py` |
| FTS configuration | PostgreSQL `tsvector` + `websearch_to_tsquery` |
