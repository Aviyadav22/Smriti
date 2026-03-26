# Gemini Embedding 2 Upgrade — Design Document

> **Purpose**: Upgrade embedding model from `gemini-embedding-001` to `gemini-embedding-2-preview`, add task_type specialization, tune dense chunk sizes, and add multi-scale section-level vectors.
> **Optimized for**: Claude Opus in ralph loop — contains full context to execute any step cold.
> **Date**: 2026-03-23 | **Project**: Smriti (d:\Startup\Smriti)
> **Approach**: B (Model Swap + task_type + Dense Chunk Tuning + Section-Level Vectors)

---

## Why This Upgrade

| Current | After Upgrade |
|---------|--------------|
| `gemini-embedding-001` | `gemini-embedding-2-preview` |
| 2,048 token context | 8,192 token context |
| MTEB Retrieval: ~62 | MTEB Retrieval: 67.71 (+9%) |
| MLEB Legal RAG: 0.422 | ~0.50 (+19%) |
| No task_type used | Asymmetric task_type on all 13 call sites |
| Dense chunks: 1200 chars | Dense chunks: 1800 chars |
| No section-level vectors | Multi-scale section vectors (new) |

**Estimated impact**: +15-30% retrieval quality, translating to ~10-15% improvement in research agent answer accuracy.

**Prerequisite**: User will delete all existing Pinecone vectors first, then re-ingest everything with the upgraded pipeline.

---

## Change 1: EmbeddingProvider Interface + GeminiEmbedder

### Interface (`backend/app/core/interfaces/embedder.py`)

Add optional `task_type` kwarg to both methods:

```python
class EmbeddingProvider(Protocol):
    async def embed_text(self, text: str, *, task_type: str | None = None) -> list[float]: ...
    async def embed_batch(self, texts: list[str], *, task_type: str | None = None) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...
```

### Provider (`backend/app/core/providers/embeddings/gemini.py`)

Pass `task_type` to `EmbedContentConfig`:

```python
config = types.EmbedContentConfig(
    output_dimensionality=self._dimension,
    task_type=task_type,  # None falls back to model default
)
```

### Config (`backend/app/core/config.py`)

```python
gemini_embedding_model: str = "gemini-embedding-2-preview"  # was "gemini-embedding-001"
```

Dimensions stay at 1536 — only 0.2% quality difference vs 3072, half the storage, and no Pinecone index recreation needed.

---

## Change 2: task_type on All 13 Call Sites

### Rule
- Embedding text for **storage/indexing** → `"RETRIEVAL_DOCUMENT"`
- Embedding text for **searching** → `"RETRIEVAL_QUERY"`
- Embedding text for **comparison** (cosine similarity) → `"SEMANTIC_SIMILARITY"`

### Complete Call Site Map

| # | File | Line | Method | New task_type |
|---|------|------|--------|---------------|
| 1 | `core/ingestion/pipeline.py` | 948 | `embedder.embed_batch(batch)` in `_embed_chunks` | `"RETRIEVAL_DOCUMENT"` |
| 2 | `core/ingestion/pipeline.py` | 456 | `embedder.embed_batch(summary_texts)` RAPTOR summaries | `"RETRIEVAL_DOCUMENT"` |
| 3 | `core/ingestion/pipeline.py` | 1142 | `_embed_chunks([], ..., texts_override=...)` in `_upsert_proposition_vectors` | `"RETRIEVAL_DOCUMENT"` (flows through `_embed_chunks`) |
| 4 | `tasks/document_tasks.py` | 249 | `embedder.embed_batch(batch_texts)` Celery ingestion | `"RETRIEVAL_DOCUMENT"` |
| 5 | `scripts/ingest_statutes.py` | ~325 | `embedder.embed_batch(batch_texts)` statute ingestion | `"RETRIEVAL_DOCUMENT"` |
| 6 | `core/search/hybrid.py` | 434 | `embedder.embed_text(query)` in `_vector_search` | `"RETRIEVAL_QUERY"` |
| 7 | `core/search/semantic_cache.py` | 96,156 | `embedder.embed_text(query)` cache lookup | `"RETRIEVAL_QUERY"` |
| 8 | `agents/nodes/worker_nodes.py` | 158 | `embedder.embed_text(nl_query)` case_law_worker fallback | `"RETRIEVAL_QUERY"` |
| 9 | `agents/nodes/worker_nodes.py` | 378 | `embedder.embed_text(original_query)` statute_worker | `"RETRIEVAL_QUERY"` |
| 10 | `agents/nodes/worker_nodes.py` | 952 | `embedder.embed_text(task["nl_query"])` graph_community_worker | `"RETRIEVAL_QUERY"` |
| 11 | `agents/nodes/research_nodes.py` | 1499 | `embedder.embed_batch(queries)` pre_warm_embeddings | `"RETRIEVAL_QUERY"` |
| 12 | `agents/nodes/common.py` | 198 | `embedder.embed_text(query)` statute_lookup_node | `"RETRIEVAL_QUERY"` |
| 13a | `agents/nodes/common.py` | 880 | `embedder.embed_batch(all_texts)` holding accuracy check | `"SEMANTIC_SIMILARITY"` |
| 13b | `agents/nodes/common.py` | 1122 | `embedder.embed_text(text_input)` cached_embed_text | `"RETRIEVAL_QUERY"` |
| 14 | `api/routes/cases.py` | 308 | `embedder.embed_text(ratio)` similar cases API | `"SEMANTIC_SIMILARITY"` |

**Implementation note for `_embed_chunks`**: Add `task_type` as a kwarg, pass through to `embedder.embed_batch(batch, task_type=task_type)`. All callers of `_embed_chunks` pass it explicitly.

**Note**: Emb 2 preview currently has a bug where task_type is ignored (returns identical vectors). Code it correctly anyway — works immediately when Google fixes it.

---

## Change 3: Dense Chunk Size Tuning

### File: `backend/app/core/ingestion/chunker.py`

| Constant | Old | New | Rationale |
|----------|-----|-----|-----------|
| `_DENSE_CHUNK_SIZE` | 1200 | 1800 | Legal holdings average 800-1500 chars. At 1200, ~30% of holdings split across chunks. At 1800, <10% split. |
| `_DENSE_CHUNK_OVERLAP` | 300 | 400 | Proportional overlap ratio preserved (22%). 400 chars ≈ 2-3 legal sentences. |

**Affected sections**: ANALYSIS, RATIO, ORDER, DISSENT, CONCURRENCE (the `_DENSE_SECTIONS` frozenset).

**Standard chunks unchanged**: 2000 chars / 200 overlap. Research shows 256-512 tokens (~1000-2000 chars) is the precision sweet spot for factoid/specific-answer retrieval.

**Impact on vector count**: ~33% fewer dense-section vectors per case. Overall per-case vectors drop from ~57 to ~50.

---

## Change 4: Section-Level Vectors (Multi-Scale Indexing)

### Concept

Alongside fine-grained chunks (2000/1800 chars), embed the **full section text** as one additional vector per eligible section. Emb 2's 8K token window makes this possible.

This creates multi-scale indexing:
- Fine-grained chunks → precise matching ("What is the Virsa Singh test?")
- Section-level vectors → broad thematic matching ("evolution of right to privacy under Article 21")
- RRF naturally combines both — proven +10-37% recall improvement in literature.

### Eligible Sections

| Section Type | Section-Level Vector? | Reason |
|-------------|----------------------|--------|
| ANALYSIS | Yes | Core legal reasoning |
| RATIO | Yes | Holdings, ratio decidendi |
| ORDER | Yes | Disposition, directions |
| DISSENT | Yes | Dissenting reasoning |
| CONCURRENCE | Yes | Concurring reasoning |
| FACTS | Yes | Factual matrix — important for "similar facts" queries |
| ARGUMENTS | No | Parties' submissions, not the court's view |
| ISSUES | No | Usually short, fits in one chunk already |
| All others | No | Low retrieval value |

Constant: `_SECTION_VECTOR_TYPES = frozenset({"ANALYSIS", "RATIO", "ORDER", "DISSENT", "CONCURRENCE", "FACTS"})`

### Minimum Section Length

Skip sections < 500 chars — too short to benefit from a separate section-level vector (already captured by one chunk).

### Smart Truncation (Head+Tail)

If section text exceeds ~30,000 chars (~8K tokens), DON'T hard-truncate at 30K. Use head+tail pattern:
- First 15,000 chars (reasoning setup)
- `\n\n[...section truncated...]\n\n`
- Last 15,000 chars (holding/conclusion)

This matches the LLM metadata extraction pattern already used in the codebase. The court's reasoning setup is at the start; the holding is at the end.

### Vector ID and Metadata

- **ID format**: `{case_id}_section_{section_type}` (e.g., `abc123_section_ANALYSIS`)
- **Metadata**:
  - All standard chunk metadata fields (case_id, court, year, case_type, etc.)
  - `vector_type: "section"` (new type)
  - `section_type`: the section type string
  - `text`: first 2000 chars (Pinecone 40KB metadata cap)
  - `char_start`, `char_end`: section boundaries
  - `section_legal_signal`: `_compute_legal_signal()` on full section text (free future boosting signal)

### Search Integration

**No changes needed to hybrid search.** Section vectors are automatically discoverable:
- `_vector_search` queries Pinecone with no `vector_type` filter by default
- Section vectors compete with chunk vectors in top_k=20
- Dedup in `_vector_search` keeps best-scoring vector per case_id — if section vector scores higher than any chunk, it wins; vice versa
- Research agent's `deduplicate_with_diversity` (max 4 per case) allows section + chunk mix naturally

### Pipeline Placement

New step 8c in `ingest_judgment()`, after:
- Step 8: Chunk upsert
- Step 8a: Proposition/ratio/headnote upsert
- Step 8b: RAPTOR section summaries

Step 8c: Section-level vector upsert (same pattern as 8b).

### Vector Count Impact

4-6 additional vectors per case. Total per case: ~55 (from ~50 after dense chunk tuning). For 43K cases: ~2.37M vectors.

---

## Change 5: Test Updates

### Chunker Tests (`backend/tests/unit/test_chunker.py`)

1. Update `test_dense_sections_get_smaller_chunks`: assertion from `<= 1200 + 50` to `<= 1800 + 50`, min chunks from `>= 3` to `>= 2` for 3000-char input
2. Add new test: 5000-char ANALYSIS section must produce `>= 3` chunks with correct overlap at multiple boundaries

### Embedder Tests (`backend/tests/unit/`)

1. Update protocol conformance test to verify `task_type` kwarg exists on both methods
2. Add unit test for GeminiEmbedder passing `task_type` to `EmbedContentConfig`
3. Add unit test for `task_type=None` backward compatibility

### Pipeline Tests

1. Test `_embed_chunks` passes `task_type` through to embedder mock
2. Test `_upsert_proposition_vectors` → `_embed_chunks` → embedder chain preserves task_type
3. Test new section-level vector creation: correct IDs, metadata, eligible sections only

### Search Tests

1. Test `_vector_search` passes `task_type="RETRIEVAL_QUERY"` to embedder
2. Test `_check_holding_accuracy` passes `task_type="SEMANTIC_SIMILARITY"`

---

## What This Design Does NOT Change

- Standard chunk size (2000 chars / 200 overlap) — research-validated sweet spot
- Pinecone index configuration (1536 dimensions, cosine metric)
- RRF weights, Cohere reranking, dedup logic
- Search pipeline structure (hybrid search → RRF → rerank → enrich)
- Contextual embedding prefix (Flash LLM) — leave as-is, optimize later
- `legal_signal` boosting in search — stored in metadata for future use, not activated now
- Any LLM prompts or agent graph wiring

---

## Execution Order

1. Interface + provider + config (foundation — everything depends on this)
2. task_type on all 13 call sites (builds on #1)
3. Dense chunk size constants (independent, small change)
4. Section-level vectors in pipeline (builds on #1 for embedding)
5. Tests for all changes
6. Re-ingest statutes + cases with upgraded pipeline
