# Gemini Embedding 2 Upgrade — Implementation Plan

> **Purpose**: Step-by-step implementation plan for upgrading from `gemini-embedding-001` to `gemini-embedding-2-preview` with task_type specialization, dense chunk tuning, and multi-scale section-level vectors.
> **Optimized for**: Claude Opus in ralph loop — each step is self-contained with full file paths, exact code locations, and verification commands.
> **Date**: 2026-03-23 | **Project**: Smriti (d:\Startup\Smriti)
> **Design doc**: `docs/plans/2026-03-23-gemini-embedding-2-upgrade-design.md`
> **Tracker**: `docs/plans/2026-03-23-gemini-embedding-2-upgrade-tracker.md`

---

## Pre-Flight Checks

Before starting ANY step, run:
```bash
cd d:/Startup/Smriti/backend && python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5
```
Record the baseline test count. Current expected: ~2039 passing. Never drop below this.

Frontend tests (run after any frontend-touching change, none expected in this plan):
```bash
cd d:/Startup/Smriti/frontend && npm test 2>&1 | tail -5
```
Current expected: ~311 passing.

---

## STEP 1: Update EmbeddingProvider Interface

**Files to modify:**
- `backend/app/core/interfaces/embedder.py`

**What to do:**

Add optional `task_type` kwarg to both protocol methods:

```python
# backend/app/core/interfaces/embedder.py

@runtime_checkable
class EmbeddingProvider(Protocol):
    """Contract for text embedding providers."""

    async def embed_text(self, text: str, *, task_type: str | None = None) -> list[float]: ...

    async def embed_batch(self, texts: list[str], *, task_type: str | None = None) -> list[list[float]]: ...

    @property
    def dimension(self) -> int: ...
```

**Verification:**
```bash
cd d:/Startup/Smriti/backend && python -c "from app.core.interfaces.embedder import EmbeddingProvider; print('OK')"
python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5
```

All existing tests must still pass — `task_type` is optional with default `None`, so no callers break.

---

## STEP 2: Update GeminiEmbedder Provider

**Files to modify:**
- `backend/app/core/providers/embeddings/gemini.py`

**What to do:**

1. Update module docstring: change `gemini-embedding-001` to `gemini-embedding-2-preview`
2. Add `task_type` parameter to both `embed_text` and `embed_batch`
3. Pass `task_type` into `EmbedContentConfig`

**Exact changes to `embed_text`:**

Find:
```python
    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string into a 1536-dim vector via Gemini."""
        response = await asyncio.wait_for(
            self._client.aio.models.embed_content(
                model=self._model,
                contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._dimension,
                ),
            ),
            timeout=60.0,
        )
```

Replace with:
```python
    async def embed_text(self, text: str, *, task_type: str | None = None) -> list[float]:
        """Embed a single text string into a 1536-dim vector via Gemini."""
        response = await asyncio.wait_for(
            self._client.aio.models.embed_content(
                model=self._model,
                contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._dimension,
                    task_type=task_type,
                ),
            ),
            timeout=60.0,
        )
```

**Exact changes to `embed_batch`:**

Find:
```python
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into 1536-dim vectors. Used during ingestion (batch 100)."""
        response = await asyncio.wait_for(
            self._client.aio.models.embed_content(
                model=self._model,
                contents=texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._dimension,
                ),
            ),
            timeout=120.0,
        )
```

Replace with:
```python
    async def embed_batch(self, texts: list[str], *, task_type: str | None = None) -> list[list[float]]:
        """Embed a batch of texts into 1536-dim vectors. Used during ingestion (batch 100)."""
        response = await asyncio.wait_for(
            self._client.aio.models.embed_content(
                model=self._model,
                contents=texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._dimension,
                    task_type=task_type,
                ),
            ),
            timeout=120.0,
        )
```

**Verification:**
```bash
cd d:/Startup/Smriti/backend && python -c "
from app.core.providers.embeddings.gemini import GeminiEmbedder
import inspect
sig = inspect.signature(GeminiEmbedder.embed_text)
assert 'task_type' in sig.parameters, 'embed_text missing task_type'
sig2 = inspect.signature(GeminiEmbedder.embed_batch)
assert 'task_type' in sig2.parameters, 'embed_batch missing task_type'
print('OK: both methods have task_type')
"
python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5
```

---

## STEP 3: Update Config — Model Name

**Files to modify:**
- `backend/app/core/config.py`

**What to do:**

Find:
```python
gemini_embedding_model: str = "gemini-embedding-001"
```

Replace with:
```python
gemini_embedding_model: str = "gemini-embedding-2-preview"
```

**Also update `.env` if it overrides this setting:**
- `backend/.env` — check for `GEMINI_EMBEDDING_MODEL`. If present, update to `gemini-embedding-2-preview`. If absent, the config.py default takes effect.

**Verification:**
```bash
cd d:/Startup/Smriti/backend && python -c "
from app.core.config import settings
assert settings.gemini_embedding_model == 'gemini-embedding-2-preview', f'Got {settings.gemini_embedding_model}'
print(f'OK: model={settings.gemini_embedding_model}, dim={settings.gemini_embedding_dimension}')
"
python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5
```

---

## STEP 4: Add task_type to Ingestion Pipeline

**Files to modify:**
- `backend/app/core/ingestion/pipeline.py`

**4a. Update `_embed_chunks` to accept and pass task_type:**

Find the function signature (line ~930):
```python
async def _embed_chunks(
    chunks: list[Chunk],
    embedder: EmbeddingProvider,
    max_retries: int = 3,
    *,
    rate_limiter: AsyncRateLimiter | None = None,
    texts_override: list[str] | None = None,
) -> list[list[float]]:
```

Replace with:
```python
async def _embed_chunks(
    chunks: list[Chunk],
    embedder: EmbeddingProvider,
    max_retries: int = 3,
    *,
    rate_limiter: AsyncRateLimiter | None = None,
    texts_override: list[str] | None = None,
    task_type: str | None = None,
) -> list[list[float]]:
```

Inside the function, find:
```python
                batch_embeddings = await embedder.embed_batch(batch)
```

Replace with:
```python
                batch_embeddings = await embedder.embed_batch(batch, task_type=task_type)
```

**4b. Update all callers of `_embed_chunks` in pipeline.py:**

Caller 1 — main chunk embedding (line ~365, inside `ingest_judgment`):
Find the `_embed_chunks(chunks, embedder, ...)` call and add `task_type="RETRIEVAL_DOCUMENT"`.

Caller 2 — `_upsert_proposition_vectors` (line ~1142):
Find:
```python
    embeddings = await _embed_chunks(
        [],  # unused — we pass texts_override
        embedder,
        rate_limiter=rate_limiter,
        texts_override=texts_to_embed,
    )
```

Replace with:
```python
    embeddings = await _embed_chunks(
        [],  # unused — we pass texts_override
        embedder,
        rate_limiter=rate_limiter,
        texts_override=texts_to_embed,
        task_type="RETRIEVAL_DOCUMENT",
    )
```

**4c. Update RAPTOR summary embedding (line ~456):**

Find the direct `embedder.embed_batch(summary_texts)` call and change to:
```python
            summary_embeddings = await embedder.embed_batch(
                summary_texts, task_type="RETRIEVAL_DOCUMENT"
            )
```

**Verification:**
```bash
cd d:/Startup/Smriti/backend && python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5
```

If any test mocks `_embed_chunks` or `embed_batch`, they may need the `task_type` kwarg added to their mock signatures. Check for `AsyncMock` or `MagicMock` instances patching the embedder.

---

## STEP 5: Add task_type to All Search Call Sites

**Files to modify:**
- `backend/app/core/search/hybrid.py`
- `backend/app/core/search/semantic_cache.py`
- `backend/app/core/agents/nodes/worker_nodes.py`
- `backend/app/core/agents/nodes/research_nodes.py`
- `backend/app/core/agents/nodes/common.py`
- `backend/app/api/routes/cases.py`
- `backend/app/tasks/document_tasks.py`

**5a. `hybrid.py` line 434 — `_vector_search`:**

Find:
```python
    query_vector = pre_embedded if pre_embedded else await embedder.embed_text(query)
```

Replace with:
```python
    query_vector = pre_embedded if pre_embedded else await embedder.embed_text(
        query, task_type="RETRIEVAL_QUERY"
    )
```

**5b. `semantic_cache.py` lines 96 and 156:**

Both calls to `embedder.embed_text(query)` → add `task_type="RETRIEVAL_QUERY"`.

**5c. `worker_nodes.py` lines 158, 378, 952:**

All three `embedder.embed_text(...)` calls → add `task_type="RETRIEVAL_QUERY"`.

**5d. `research_nodes.py` line 1499 — `pre_warm_embeddings_node`:**

Find:
```python
        vectors = await embedder.embed_batch(queries)
```

Replace with:
```python
        vectors = await embedder.embed_batch(queries, task_type="RETRIEVAL_QUERY")
```

**5e. `common.py` line 198 — `statute_lookup_node` vector search:**

`embedder.embed_text(query)` → add `task_type="RETRIEVAL_QUERY"`.

**5f. `common.py` line 880 — `_check_holding_accuracy`:**

`embedder.embed_batch(all_texts)` → add `task_type="SEMANTIC_SIMILARITY"`.

**5g. `common.py` line 1122 — `cached_embed_text`:**

`embedder.embed_text(text_input)` → add `task_type="RETRIEVAL_QUERY"`.

**5h. `cases.py` line 308 — similar cases API:**

`embedder.embed_text(ratio)` → add `task_type="SEMANTIC_SIMILARITY"`.

**5i. `document_tasks.py` line 249 — Celery ingestion:**

`embedder.embed_batch(batch_texts)` → add `task_type="RETRIEVAL_DOCUMENT"`.

**Verification:**
```bash
cd d:/Startup/Smriti/backend && python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5
```

If mocks break, update mock embedder signatures. The `MockEmbedder` in test fixtures must accept `**kwargs` or explicit `task_type=None`.

---

## STEP 6: Update Dense Chunk Constants

**Files to modify:**
- `backend/app/core/ingestion/chunker.py`

**What to do:**

Find:
```python
_DENSE_CHUNK_SIZE: int = 1200
_DENSE_CHUNK_OVERLAP: int = 300
```

Replace with:
```python
_DENSE_CHUNK_SIZE: int = 1800
_DENSE_CHUNK_OVERLAP: int = 400
```

**No other code changes.** The constants are already used by `chunk_judgment()` via `effective_chunk_size` / `effective_overlap` selection.

**Verification:**
```bash
cd d:/Startup/Smriti/backend && python -c "
from app.core.ingestion.chunker import _DENSE_CHUNK_SIZE, _DENSE_CHUNK_OVERLAP
assert _DENSE_CHUNK_SIZE == 1800, f'Got {_DENSE_CHUNK_SIZE}'
assert _DENSE_CHUNK_OVERLAP == 400, f'Got {_DENSE_CHUNK_OVERLAP}'
print('OK')
"
```

---

## STEP 7: Add Section-Level Vector Creation

**Files to modify:**
- `backend/app/core/ingestion/pipeline.py`
- `backend/app/core/ingestion/chunker.py` (add `_compute_legal_signal` import if not already available, and `_SECTION_VECTOR_TYPES` constant)

**7a. Add constants to chunker.py:**

Add near the top of the file, after `_DENSE_SECTIONS`:
```python
# Section types eligible for section-level embedding vectors (multi-scale indexing)
_SECTION_VECTOR_TYPES: frozenset[str] = frozenset({
    "ANALYSIS", "RATIO", "ORDER", "DISSENT", "CONCURRENCE", "FACTS",
})

# Minimum section length for section-level vectors (chars)
_MIN_SECTION_VECTOR_LENGTH: int = 500

# Max chars for section-level embedding (~8K tokens for Gemini Emb 2)
_MAX_SECTION_VECTOR_CHARS: int = 30_000
```

Also export `_compute_legal_signal` if it's currently a private function. If it's already accessible from the module, no change needed.

**7b. Add `_build_section_vectors` helper in pipeline.py:**

Add a new function after `_upsert_proposition_vectors`:

```python
async def _upsert_section_vectors(
    case_id: str,
    sections: list,  # list of Section objects from chunker
    metadata: CaseMetadata,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    *,
    rate_limiter: AsyncRateLimiter | None = None,
    full_text: str | None = None,
) -> tuple[int, list[str]]:
    """Create section-level vectors for multi-scale indexing.

    Embeds the full text of eligible sections (ANALYSIS, RATIO, ORDER,
    DISSENT, CONCURRENCE, FACTS) as single vectors, complementing the
    fine-grained chunk vectors. Leverages Gemini Embedding 2's 8K token window.

    Returns (count, vector_ids).
    """
    from app.core.ingestion.chunker import (
        _SECTION_VECTOR_TYPES,
        _MIN_SECTION_VECTOR_LENGTH,
        _MAX_SECTION_VECTOR_CHARS,
        _compute_legal_signal,
    )

    vectors: list[dict] = []
    texts_to_embed: list[str] = []
    vector_ids: list[str] = []

    base_meta = {
        "case_id": case_id,
        "court": metadata.court or "",
        "year": metadata.year or 0,
        "case_type": metadata.case_type or "",
        "bench_type": metadata.bench_type or "",
        "title": (metadata.title or "")[:200],
        "citation": metadata.citation or "",
        "acts_cited": list(metadata.acts_cited[:25]) if metadata.acts_cited else [],
        "document_type": "case_law",
    }

    for section in sections:
        if section.type not in _SECTION_VECTOR_TYPES:
            continue
        if len(section.text) < _MIN_SECTION_VECTOR_LENGTH:
            continue

        # Smart truncation: head + tail (preserve reasoning setup + holding)
        section_text = section.text
        if len(section_text) > _MAX_SECTION_VECTOR_CHARS:
            half = _MAX_SECTION_VECTOR_CHARS // 2
            section_text = (
                section_text[:half]
                + "\n\n[...section truncated...]\n\n"
                + section_text[-half:]
            )

        vid = f"{case_id}_section_{section.type}"
        vector_ids.append(vid)
        texts_to_embed.append(section_text)

        vectors.append({
            "id": vid,
            "metadata": {
                **base_meta,
                "vector_type": "section",
                "section_type": section.type,
                "text": section.text[:2000],  # Pinecone 40KB metadata cap
                "char_start": section.start,
                "char_end": section.end,
                "section_legal_signal": _compute_legal_signal(section.text),
            },
        })

    if not texts_to_embed:
        return 0, []

    # Embed all section texts
    embeddings = await _embed_chunks(
        [],
        embedder,
        rate_limiter=rate_limiter,
        texts_override=texts_to_embed,
        task_type="RETRIEVAL_DOCUMENT",
    )

    for vec, emb in zip(vectors, embeddings):
        vec["values"] = emb

    # Upsert in batches
    for batch_start in range(0, len(vectors), _EMBED_BATCH_SIZE):
        batch = vectors[batch_start : batch_start + _EMBED_BATCH_SIZE]
        await vector_store.upsert(batch)

    logger.info("Upserted %d section-level vectors for %s", len(vectors), case_id)
    return len(vectors), vector_ids
```

**7c. Call from `ingest_judgment`:**

In the main `ingest_judgment` function, after step 8b (RAPTOR summaries), add step 8c:

```python
# 8c. SECTION-LEVEL VECTORS (multi-scale indexing, Gemini Emb 2)
try:
    section_count, section_vector_ids = await _upsert_section_vectors(
        str(case_id),
        sections,  # from step 3 (detect_judgment_sections)
        metadata,
        embedder,
        vector_store,
        rate_limiter=embed_rate_limiter or rate_limiter,
        full_text=full_text,
    )
    all_vector_ids.extend(section_vector_ids)
    logger.info("Step 8c: Upserted %d section vectors", section_count)
except Exception as exc:
    logger.warning("Step 8c section vectors failed (non-fatal): %s", exc)
```

**Important**: The `sections` variable must be available at this point in `ingest_judgment`. Verify it's still in scope from step 3 (section detection). If not, save it to a local variable earlier.

**Also important**: `all_vector_ids` (used for stale vector cleanup) must include section vector IDs so they don't get deleted as stale.

**Verification:**
```bash
cd d:/Startup/Smriti/backend && python -c "
from app.core.ingestion.chunker import _SECTION_VECTOR_TYPES, _MIN_SECTION_VECTOR_LENGTH, _MAX_SECTION_VECTOR_CHARS
print(f'Section types: {_SECTION_VECTOR_TYPES}')
print(f'Min length: {_MIN_SECTION_VECTOR_LENGTH}')
print(f'Max chars: {_MAX_SECTION_VECTOR_CHARS}')
"
python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5
```

---

## STEP 8: Update Tests

**Files to modify:**
- `backend/tests/unit/test_chunker.py`
- `backend/tests/unit/test_provider_contracts.py`
- New: `backend/tests/unit/test_embedding_task_types.py`
- Any test files with `MockEmbedder` or embedder mocks

**8a. Update chunker tests:**

In `test_dense_sections_get_smaller_chunks` — update assertion:
```python
# Old:
assert len(chunk.text) <= 1200 + 50
# New:
assert len(chunk.text) <= 1800 + 50
```

Update minimum chunk count expectation for 3000-char input:
```python
# Old:
assert len(chunks) >= 3
# New:
assert len(chunks) >= 2
```

Add new test for multi-boundary verification:
```python
def test_dense_section_multiple_boundaries():
    """5000-char ANALYSIS section produces 3+ chunks with correct overlap."""
    analysis_text = "The court held that this principle applies. " * 125  # ~5500 chars
    sections = [Section(type="ANALYSIS", start=0, end=len(analysis_text), text=analysis_text)]
    chunks = chunk_judgment(analysis_text, sections, case_id="test")
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk.text) <= 1800 + 50
```

**8b. Update provider contract test:**

Verify `task_type` kwarg exists:
```python
def test_gemini_embedder_supports_task_type(self) -> None:
    import inspect
    from app.core.providers.embeddings.gemini import GeminiEmbedder
    sig_text = inspect.signature(GeminiEmbedder.embed_text)
    sig_batch = inspect.signature(GeminiEmbedder.embed_batch)
    assert "task_type" in sig_text.parameters
    assert "task_type" in sig_batch.parameters
```

**8c. Fix all MockEmbedder instances:**

Search for all mock embedders across tests:
```bash
cd d:/Startup/Smriti/backend && grep -rn "MockEmbedder\|mock.*embed_text\|mock.*embed_batch\|AsyncMock.*embed" tests/ --include="*.py"
```

For each mock, ensure `embed_text` and `embed_batch` accept `**kwargs` or explicit `task_type=None`:
```python
# If using a class-based mock:
async def embed_text(self, text: str, *, task_type: str | None = None) -> list[float]:
    return [0.1] * 1536

async def embed_batch(self, texts: list[str], *, task_type: str | None = None) -> list[list[float]]:
    return [[0.1] * 1536 for _ in texts]
```

**8d. Add section vector test:**

```python
def test_section_vector_creation():
    """Eligible sections produce section-level vectors with correct metadata."""
    # Test with mock sections, verify:
    # - Only _SECTION_VECTOR_TYPES get vectors
    # - Sections < 500 chars are skipped
    # - Vector ID format: {case_id}_section_{type}
    # - metadata has vector_type="section", section_legal_signal computed
    # - Smart truncation works for >30K char sections (head+tail)
```

**Verification:**
```bash
cd d:/Startup/Smriti/backend && python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5
```

All tests must pass. Test count should increase by 4-6 (new tests added).

---

## STEP 9: Final Verification

**9a. Full test suite:**
```bash
cd d:/Startup/Smriti/backend && python -m pytest tests/ -x -q --tb=short
```

**9b. Import chain verification (no circular imports):**
```bash
cd d:/Startup/Smriti/backend && python -c "
from app.core.interfaces.embedder import EmbeddingProvider
from app.core.providers.embeddings.gemini import GeminiEmbedder
from app.core.ingestion.pipeline import ingest_judgment
from app.core.ingestion.chunker import _SECTION_VECTOR_TYPES, _DENSE_CHUNK_SIZE
from app.core.search.hybrid import hybrid_search
print('All imports OK')
print(f'Model: gemini-embedding-2-preview')
print(f'Dense chunk: {_DENSE_CHUNK_SIZE}')
print(f'Section vector types: {_SECTION_VECTOR_TYPES}')
"
```

**9c. Grep for any remaining bare embed calls without task_type:**
```bash
cd d:/Startup/Smriti/backend && grep -rn "embed_text\|embed_batch" app/ --include="*.py" | grep -v "task_type" | grep -v "Protocol\|Protocol\|def embed\|# \|import\|__"
```

Any remaining calls without `task_type` are bugs — fix them.

---

## Post-Implementation: Re-Ingestion (NOT part of this plan)

After all steps pass:
1. Delete all vectors from Pinecone index `smriti-legal` (user handles this)
2. Re-run statute ingestion: `python scripts/ingest_statutes.py`
3. Re-run case ingestion for existing 112 cases
4. Verify search quality with sample queries
5. Proceed with 43K case ingestion

---

## Step Summary

| Step | What | Files | Dependencies |
|------|------|-------|-------------|
| 1 | EmbeddingProvider interface + task_type | `interfaces/embedder.py` | None |
| 2 | GeminiEmbedder + task_type | `providers/embeddings/gemini.py` | Step 1 |
| 3 | Config model name | `config.py`, `.env` | None |
| 4 | Pipeline task_type (ingestion side) | `ingestion/pipeline.py` | Steps 1-2 |
| 5 | Search task_type (13 call sites) | `hybrid.py`, `semantic_cache.py`, `worker_nodes.py`, `research_nodes.py`, `common.py`, `cases.py`, `document_tasks.py` | Steps 1-2 |
| 6 | Dense chunk constants | `chunker.py` | None |
| 7 | Section-level vectors | `pipeline.py`, `chunker.py` | Steps 1-2, 4 |
| 8 | Tests | `test_chunker.py`, `test_provider_contracts.py`, new test files, all mock fixtures | Steps 1-7 |
| 9 | Final verification | All | Steps 1-8 |

**Parallelizable**: Steps 3 and 6 are independent of each other and of steps 4-5. Steps 4 and 5 are independent of each other (both depend on 1-2). Step 7 depends on 4.
