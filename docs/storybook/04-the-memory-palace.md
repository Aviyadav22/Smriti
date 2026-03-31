# Chapter 4: The Memory Palace

---

Now comes the magic part.

Smriti has read the PDF. She's extracted the metadata. She has clean text and structured data. But how does she *remember* 35,000 judgments and find the right one when you ask a question?

The answer lies in **embeddings** — and they're one of the most beautiful ideas in AI.

---

## What Are Embeddings?

Imagine you could take any sentence and place it as a dot in a massive room with 1,536 dimensions. (Yes, that's impossible to visualize, but bear with me.)

Sentences that *mean* similar things end up close together. Sentences that mean different things end up far apart.

```
"The accused was convicted of murder"
    ↓ embed
    [0.023, -0.145, 0.891, ... 1,536 numbers]

"The defendant was found guilty of homicide"
    ↓ embed
    [0.025, -0.142, 0.888, ... 1,536 numbers]

These two vectors are very close → Smriti knows they mean the same thing!
Even though they share almost no keywords.
```

This is what keyword search can never do. It matches *words*. Embeddings match *meaning*.

---

## Gemini's Embedding Model

Smriti uses Google's `gemini-embedding-2-preview` — a model that produces 1,536-dimensional vectors. But it has a superpower most embedding models don't: **task-type awareness**.

When creating an embedding, you tell Gemini *what you're going to use it for*:

| Task Type | When Used | What It Does |
|-----------|-----------|------------|
| `RETRIEVAL_DOCUMENT` | When storing a chunk of text | Optimized for being *found* |
| `RETRIEVAL_QUERY` | When a user searches | Optimized for *finding* documents |
| `SEMANTIC_SIMILARITY` | When comparing two texts | Optimized for measuring similarity |

Why does this matter? Because the way you embed a document should be different from how you embed a question about it. "The court held that bail is a right" (document) and "Is bail a right?" (query) mean similar things but have different structures. Task-type awareness handles this.

---

## Legal-Aware Chunking: Not Just Any Text

You can't just feed a 50-page judgment into the embedding model. It has a token limit, and more importantly, a single embedding for 50 pages would be too vague to be useful.

Instead, Smriti **chunks** the judgment — breaks it into smaller pieces. But not randomly.

### The Problem With Dumb Chunking

If you just split every 2,000 characters, you might cut a sentence in half. Or split the ratio decidendi across two chunks. Or put the facts and the holding in the same chunk, diluting the meaning of both.

### Legal-Aware Chunking

Smriti first detects the **sections** of the judgment:

```
JUDGMENT TEXT
├── FACTS (What happened)
├── ISSUES (What the court needs to decide)
├── ARGUMENTS (What each side said)
│   ├── Petitioner's arguments
│   └── Respondent's arguments
├── ANALYSIS (The court's reasoning)
├── RATIO DECIDENDI (The legal principle)
├── ORDER (The final decision)
├── DISSENT (If any judge disagreed)
└── CONCURRENCE (If a judge agreed but for different reasons)
```

Different sections get different treatment:

| Section Type | Chunk Size | Overlap | Why |
|-------------|-----------|---------|-----|
| Normal (FACTS, ARGUMENTS) | 2,000 chars | 200 chars | Standard information density |
| Dense (ANALYSIS, RATIO, ORDER, DISSENT) | 1,200 chars | 300 chars | Higher information density — smaller chunks preserve nuance |

**Overlap** means the end of one chunk repeats at the beginning of the next. This prevents information loss at chunk boundaries — if a crucial sentence sits right at the split point, both chunks will contain it.

Additional rules:
- **Sentence-boundary aware**: Never split mid-sentence
- **Paragraph number tracking**: Each chunk knows which paragraphs it contains
- **Section-tagged**: Each chunk carries its section label (FACTS, RATIO, etc.)
- **Deduplication**: No two chunks from the same paragraph can start within 50 characters of each other

> **ADR-012**: Legal-aware chunking over fixed-size splitting.

---

## Seven Types of Memory

Here's where Smriti gets really clever. She doesn't just create one embedding per chunk. She creates **seven different types of vectors**, all stored in the same Pinecone index:

| Vector Type | What It Contains | Why It Exists |
|-------------|-----------------|--------------|
| **chunk** | Regular text chunk | The workhorse — basic search |
| **proposition** | Single legal statement extracted by AI | "Bail is a right, not a privilege" — precise, searchable statements |
| **ratio** | The ratio decidendi section | The legal principle — what the case *decided* |
| **headnote** | Structured case summary | Quick overview for ranking |
| **statute** | Text of a statute section | "Section 302 IPC: Punishment for murder..." |
| **summary** | AI-generated case summary | High-level understanding |
| **community** | Summary of a citation cluster | "These 15 cases all deal with bail under NDPS Act" |

All seven types live in the **same Pinecone index**, differentiated by a `vector_type` metadata field. When searching, Smriti can search all types or filter to specific ones.

**The boost**: When the research agent searches (not regular user search), `proposition`, `ratio`, and `headnote` vectors get a **1.5x boost** in ranking. These types are more authoritative for legal research than raw text chunks.

---

## Contextual Prefixes: Giving Chunks Context

A chunk like "The appeal is accordingly dismissed" is useless without context. *Whose* appeal? *Which* case?

Smriti optionally adds a **contextual prefix** to each chunk before embedding:

```
Before:
  "The appeal is accordingly dismissed with costs."

After:
  "This is from the ORDER section of State of Maharashtra v. Rajesh Kumar
   (2024) 3 SCC 145, a Criminal Appeal before the Supreme Court.
   The appeal is accordingly dismissed with costs."
```

This prefix is generated by Gemini Flash (cheap and fast) — one LLM call per chunk, with 10 running concurrently. The original text is preserved for display; only the enriched version gets embedded.

The effect is dramatic. A search for "murder appeals dismissed by Supreme Court in 2024" now matches this chunk, even though the original text only says "appeal is accordingly dismissed."

---

## The Storage Strategy

### Pinecone: The Vector Store

All vectors go to Pinecone, a managed vector database. Each vector carries metadata:

```json
{
  "id": "case_abc123_chunk_7",
  "values": [0.023, -0.145, ...],  // 1,536 dimensions
  "metadata": {
    "case_id": "abc123",
    "title": "State of Maharashtra v. Rajesh Kumar",
    "citation": "(2024) 3 SCC 145",
    "court": "Supreme Court of India",
    "year": 2024,
    "vector_type": "chunk",
    "section": "RATIO",
    "text": "The court held that..."  // for display
  }
}
```

This metadata enables **filtered search**: "Find chunks about bail, but only from Supreme Court cases after 2020."

### The Safety Dance: New First, Delete Later

When re-ingesting a case (fixing errors, adding new vector types), Smriti:
1. **Upserts new vectors first**
2. **Then deletes old ones**

Never the other way around. If step 2 fails, you have duplicates (annoying but recoverable). If you delete first and the upsert fails, you've lost data (catastrophic).

### Deduplication: Don't Embed What You've Already Embedded

Each document gets a **text_hash** (SHA-256 of the normalized text). If a judgment has already been ingested (same hash), skip the entire pipeline. This saves expensive LLM and embedding API calls.

---

## The Numbers

As of March 2026:

| Metric | Value |
|--------|-------|
| Cases ingested | ~35,000 |
| Statute sections | 2,932 (from 8 acts) |
| Average chunks per case | ~43 |
| Total chunk vectors | ~1.5 million |
| Total proposition vectors | ~105,000 |
| Estimated total vectors | ~2.5 million |
| Vector dimensions | 1,536 |
| Batch size | 100 texts per API call |

---

> **Next: [Chapter 5 — The Art of Finding →](./05-the-art-of-finding.md)**
>
> *Where keyword search meets semantic search, and a reranker plays referee.*

---

### In the Code

| What | Where |
|------|-------|
| Chunking logic | `backend/app/core/ingestion/chunker.py` |
| Contextual embeddings | [backend/app/core/ingestion/contextual_embeddings.py](../../backend/app/core/ingestion/contextual_embeddings.py) |
| Embedding provider | [backend/app/core/providers/embeddings/gemini.py](../../backend/app/core/providers/embeddings/gemini.py) |
| Embedding interface | [backend/app/core/interfaces/embedder.py](../../backend/app/core/interfaces/embedder.py) |
| Vector upsert logic | [backend/app/core/ingestion/pipeline.py](../../backend/app/core/ingestion/pipeline.py) → `_upsert_vectors()` |
| Pinecone provider | `backend/app/core/providers/vector/pinecone_store.py` |
| Multi-vector types | Pipeline creates chunk, proposition, ratio, headnote, statute, summary, community |
