# Technical Debt Audit Fixes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Address 9 technical debt items identified during codebase audit, covering DB transactions, Pinecone metadata docs, Cloud Run config, Celery deployment, FTS ranking docs, RRF tuning, citation confidence, and graph retry.

**Architecture:** Fixes are isolated and independent — each issue maps to 1-2 files. Most changes are config, documentation, or small code additions. Two items (m2, m5, m7, m9) are "document/accept" — the current behavior is correct but needs explicit documentation.

**Tech Stack:** Python 3.12, FastAPI, PostgreSQL, Pinecone, Neo4j, Celery, Cloud Run, Docker

---

## Issue Classification

| ID | Verdict | Action |
|----|---------|--------|
| m1 | **Fix** | Wrap ingestion status update in explicit transaction |
| m2 | **Document** | Add docstring + log warning when text is truncated |
| m3 | **Fix** | Add `--concurrency` to Cloud Run deploy script |
| m4 | **Fix** | Add worker Dockerfile + deploy script step |
| m5 | **Document** | Add ADR explaining ts_rank_cd choice |
| m6 | **Fix** | Make RRF k configurable per query strategy |
| m7 | **Document** | Add confidence field to Citation dataclass |
| m8 | **Fix** | Add async retry queue for failed graph builds |
| m9 | **Accept** | Already documented as local-only; no change needed |

---

### Task 1: m1 — Explicit Transaction for Ingestion Status Update

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py:225-235`
- Test: `backend/tests/unit/test_pipeline_transaction.py` (create)

**Context:** Currently the `UPDATE cases SET ingestion_status = 'processing'` at line 229 relies on SQLAlchemy's implicit transaction. If the session auto-commits or the connection drops between the status write and the bulk commit at line 314, we get an orphaned "processing" state. The fix wraps the entire ingestion operation in an explicit `async with db.begin()` block.

**Step 1: Write the failing test**

```python
"""Tests for explicit transaction management in the ingestion pipeline."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

from app.core.ingestion.pipeline import ingest_case


@pytest.mark.asyncio
async def test_processing_status_uses_explicit_transaction():
    """Verify that setting ingestion_status='processing' happens inside
    an explicit begin() transaction block, not implicitly."""
    mock_db = AsyncMock()
    mock_begin_ctx = AsyncMock()
    mock_db.begin.return_value = mock_begin_ctx
    # Make begin() work as async context manager
    mock_begin_ctx.__aenter__ = AsyncMock(return_value=mock_begin_ctx)
    mock_begin_ctx.__aexit__ = AsyncMock(return_value=False)

    # We expect the pipeline to call db.begin() before any execute calls
    # The pipeline will fail because other mocks aren't set up, but we
    # just need to verify begin() was called
    with pytest.raises(Exception):
        await ingest_case(
            db=mock_db,
            case_id="test-case",
            pdf_path="/fake/path.pdf",
            vector_store=AsyncMock(),
            graph_store=AsyncMock(),
            embedder=AsyncMock(),
            llm=AsyncMock(),
        )

    mock_db.begin.assert_called()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_pipeline_transaction.py -v`
Expected: FAIL — `begin()` not called in current code

**Step 3: Implement the fix**

In `pipeline.py`, wrap the processing status update and subsequent operations inside `async with db.begin()`. Change lines ~225-235 from:

```python
# Mark ingestion as in-progress
await db.execute(
    text("UPDATE cases SET ingestion_status = 'processing' WHERE id = :id"),
    {"id": case_id},
)

db_committed = False
try:
```

To:

```python
# Mark ingestion as in-progress inside explicit transaction
async with db.begin():
    await db.execute(
        text("UPDATE cases SET ingestion_status = 'processing' WHERE id = :id"),
        {"id": case_id},
    )

db_committed = False
try:
```

Note: The `begin()` block auto-commits on exit. The subsequent bulk writes at line ~314 already have their own `await db.commit()`. This change only scopes the initial status flip to its own atomic transaction, so a crash between the status update and the later commit won't leave an orphaned "processing" row — the status flip either commits or rolls back.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_pipeline_transaction.py -v`
Expected: PASS

**Step 5: Run full pipeline tests for regressions**

Run: `cd backend && python -m pytest tests/unit/test_pipeline_citation_equivalents.py tests/unit/test_pipeline_treatment.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py backend/tests/unit/test_pipeline_transaction.py
git commit -m "fix(m1): wrap ingestion status update in explicit transaction"
```

---

### Task 2: m2 — Document Pinecone Metadata Text Cap + Add Truncation Warning

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py:678-682`
- Test: `backend/tests/unit/test_pipeline_pinecone_metadata.py` (create)

**Context:** `chunk.text[:2000]` at line 681 silently truncates. The chunker targets 2000 chars so most chunks fit, but oversize chunks lose data without any log. Full text is in PostgreSQL, so this is fine — but it should be documented and logged.

**Step 1: Write the failing test**

```python
"""Tests for Pinecone metadata truncation logging."""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest

from app.core.ingestion.pipeline import _upsert_vectors
from app.core.ingestion.metadata import CaseMetadata


@pytest.mark.asyncio
async def test_upsert_vectors_logs_warning_on_text_truncation(caplog):
    """When chunk text exceeds 2000 chars, a warning should be logged."""
    from app.core.ingestion.chunker import Chunk

    long_chunk = Chunk(
        chunk_index=0,
        text="x" * 2500,
        section_type="judgment",
        opinion_author=None,
        para_start=1,
        para_end=5,
    )
    metadata = CaseMetadata(
        title="Test Case", court="SC", year=2024, citation="2024 INSC 1",
        case_type="civil", jurisdiction="original", bench_type="division",
        disposal_nature="allowed", judge=[], acts_cited=[],
        sections_cited=[], author_judge=None, date_of_judgment=None,
        case_number=None, is_reportable=None, headnotes=None,
        outcome_summary=None,
    )
    mock_vector_store = AsyncMock()

    with caplog.at_level(logging.WARNING):
        await _upsert_vectors(
            case_id="test-1",
            chunks=[long_chunk],
            embeddings=[[0.1] * 1536],
            metadata=metadata,
            vector_store=mock_vector_store,
        )

    assert any("truncated" in record.message.lower() for record in caplog.records)
    # Verify the text in the upserted vector is capped at 2000
    upserted = mock_vector_store.upsert.call_args[0][0]
    assert len(upserted[0]["metadata"]["text"]) == 2000
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_pipeline_pinecone_metadata.py -v`
Expected: FAIL — no warning logged

**Step 3: Implement the fix**

In `pipeline.py` `_upsert_vectors`, around line 681, change:

```python
                "text": chunk.text[:2000],  # Pinecone metadata size limit
```

To:

```python
                # Pinecone metadata value limit: 2000 chars.
                # Full text lives in PostgreSQL cases.full_text — this is
                # only used for snippet display in vector search results.
                "text": chunk.text[:2000],
```

And add the truncation warning before the loop (after `vectors: list[dict] = []`):

```python
    vectors: list[dict] = []
    for chunk, embedding in zip(chunks, embeddings):
        if len(chunk.text) > 2000:
            logger.warning(
                "Chunk %s_%d text truncated from %d to 2000 chars for Pinecone metadata",
                case_id, chunk.chunk_index, len(chunk.text),
            )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_pipeline_pinecone_metadata.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py backend/tests/unit/test_pipeline_pinecone_metadata.py
git commit -m "docs(m2): document Pinecone text cap, log truncation warning"
```

---

### Task 3: m3 — Add Cloud Run Concurrency Config

**Files:**
- Modify: `scripts/deploy.sh`

**Context:** Cloud Run defaults to 80 concurrent requests per instance. With a single-process uvicorn (async), this is reasonable for I/O-bound FastAPI routes, but should be explicit. The audit suggests `--concurrency=256` — however, with a single uvicorn worker and no gunicorn, 256 concurrent requests will be handled in a single event loop. A safer value is 80-100 for now, made explicit. Also add `--cpu-throttling` disabled for consistent performance.

**Step 1: Read the current deploy script**

Read `scripts/deploy.sh` to find the exact `gcloud run deploy smriti-backend` command.

**Step 2: Add `--concurrency` flag to backend deploy**

In the `gcloud run deploy smriti-backend` command, add:

```bash
--concurrency=80 \
```

This makes the default explicit. When we add gunicorn with multiple workers later, we can raise this to 256.

**Step 3: Add `--concurrency` flag to frontend deploy**

In the `gcloud run deploy smriti-frontend` command, add:

```bash
--concurrency=80 \
```

**Step 4: Commit**

```bash
git add scripts/deploy.sh
git commit -m "fix(m3): add explicit Cloud Run concurrency config"
```

---

### Task 4: m4 — Add Celery Worker Dockerfile and Deploy Script

**Files:**
- Create: `backend/Dockerfile.worker`
- Modify: `scripts/deploy.sh`

**Context:** `worker.py` and `app/tasks/` exist but have no deployment path. Tasks queued via the API are never consumed in production.

**Step 1: Create worker Dockerfile**

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
COPY app/ app/
RUN addgroup --system app && adduser --system --ingroup app app
USER app

CMD ["celery", "-A", "app.worker:celery_app", "worker", "--loglevel=info", "--concurrency=2"]
```

**Step 2: Add worker deploy step to deploy.sh**

After the backend deploy block, add a new section:

```bash
echo "--- Deploying Celery Worker ---"

gcloud builds submit \
  --tag "$REGION-docker.pkg.dev/$PROJECT_ID/smriti/smriti-worker:$TAG" \
  --project "$PROJECT_ID" \
  -f Dockerfile.worker \
  backend/

# Cloud Run Jobs (always-on worker) or Cloud Run Service with min-instances=1
gcloud run deploy smriti-worker \
  --image "$REGION-docker.pkg.dev/$PROJECT_ID/smriti/smriti-worker:$TAG" \
  --region "$REGION" \
  --platform managed \
  --no-allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --timeout 3600 \
  --execution-environment gen2 \
  --set-secrets "DATABASE_URL=DATABASE_URL:latest,REDIS_URL=REDIS_URL:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,PINECONE_API_KEY=PINECONE_API_KEY:latest,PINECONE_HOST=PINECONE_HOST:latest,NEO4J_URI=NEO4J_URI:latest,NEO4J_PASSWORD=NEO4J_PASSWORD:latest,COHERE_API_KEY=COHERE_API_KEY:latest,SARVAM_API_KEY=SARVAM_API_KEY:latest" \
  --no-cpu-throttling \
  --project "$PROJECT_ID"
```

**Step 3: Commit**

```bash
git add backend/Dockerfile.worker scripts/deploy.sh
git commit -m "fix(m4): add Celery worker Dockerfile and deploy script step"
```

---

### Task 5: m5 — Document ts_rank_cd Choice as ADR

**Files:**
- Modify: `docs/DECISIONS.md`
- Modify: `backend/app/core/search/fulltext.py:69-71` (add inline comment)

**Context:** `ts_rank_cd` (cover density) is the correct choice for legal text — it rewards proximity of query terms, which matters for multi-word legal phrases like "fundamental rights under Article 21". BM25 would require `pg_bm25` extension (not available on Cloud SQL). This just needs documentation.

**Step 1: Add ADR to DECISIONS.md**

Append a new ADR:

```markdown
### ADR-XX: FTS Ranking Uses ts_rank_cd (Cover Density), Not BM25

**Status:** Accepted
**Date:** 2026-03-17

**Context:** PostgreSQL offers `ts_rank` (frequency-based) and `ts_rank_cd` (cover density). BM25 would require the `pg_bm25` or `paradedb` extension, unavailable on Cloud SQL.

**Decision:** Use `ts_rank_cd` because:
1. Cover density rewards proximity of query terms — critical for legal phrases ("breach of contract", "Article 21 of the Constitution")
2. Legal queries tend to be multi-word and phrase-heavy; proximity matters more than raw frequency
3. Native PostgreSQL, no extension dependencies
4. Our hybrid pipeline (FTS + vector + Cohere reranker) compensates for any BM25 advantages via semantic reranking

**Consequences:** FTS alone may slightly under-rank documents where terms appear frequently but spread apart. The Cohere reranker mitigates this in the final ranking stage.
```

**Step 2: Add inline comment to fulltext.py**

At line 71, expand the comment:

```python
        # ts_rank_cd = cover density ranking: rewards proximity of query terms.
        # Chosen over ts_rank (frequency) for legal text where phrase proximity
        # matters (see ADR in DECISIONS.md). BM25 not available on Cloud SQL.
        f"ts_rank_cd(searchable_text, ({tsquery_expr})) AS rank, "
```

**Step 3: Commit**

```bash
git add docs/DECISIONS.md backend/app/core/search/fulltext.py
git commit -m "docs(m5): ADR for ts_rank_cd over BM25 in FTS ranking"
```

---

### Task 6: m6 — Per-Strategy RRF k Configuration

**Files:**
- Modify: `backend/app/core/config.py:88`
- Modify: `backend/app/core/search/hybrid.py:236-247`
- Test: `backend/tests/unit/test_hybrid_search.py`

**Context:** RRF k=60 is a single value for all query strategies. Research suggests lower k (20-30) for keyword-heavy queries (steeper rank drop-off rewards exact matches) and higher k (60-80) for balanced/vector-heavy (flatter curve for semantic diversity). The `rrf_merge` function already accepts `k` as a parameter.

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_rrf_k_varies_by_strategy():
    """Different query strategies should use different RRF k values."""
    # keyword_heavy should use a lower k than balanced
    from app.core.search.hybrid import rrf_merge

    ranked = [("doc1", 1.0), ("doc2", 0.9), ("doc3", 0.8)]

    result_low_k = rrf_merge([ranked], k=30)
    result_high_k = rrf_merge([ranked], k=60)

    # With lower k, the score difference between rank 1 and rank 3 is larger
    # k=30: 1/31 - 1/33 = 0.00196  |  k=60: 1/61 - 1/63 = 0.00052
    low_k_spread = result_low_k[0][1] - result_low_k[2][1]
    high_k_spread = result_high_k[0][1] - result_high_k[2][1]
    assert low_k_spread > high_k_spread
```

**Step 2: Run test to verify behavior**

Run: `cd backend && python -m pytest tests/unit/test_hybrid_search.py::test_rrf_k_varies_by_strategy -v`
Expected: PASS (this tests the math, not the integration)

**Step 3: Add per-strategy k config to settings**

In `config.py`, replace line 88:

```python
    search_rrf_k: int = 60
```

With:

```python
    search_rrf_k: int = 60  # default / balanced
    search_rrf_k_keyword_heavy: int = 30
    search_rrf_k_vector_heavy: int = 60
```

**Step 4: Write integration test for strategy-based k selection**

```python
@pytest.mark.asyncio
async def test_hybrid_search_uses_strategy_rrf_k(mock_settings):
    """hybrid_search should pick RRF k based on query strategy."""
    # Patch settings to have different k values
    mock_settings.search_rrf_k = 60
    mock_settings.search_rrf_k_keyword_heavy = 30
    mock_settings.search_rrf_k_vector_heavy = 60
    # ... (full mock setup following existing test patterns in test_hybrid_search.py)
```

**Step 5: Update hybrid.py to use per-strategy k**

In `hybrid.py`, around lines 236-247, change:

```python
    strategy_weights: dict[str, list[float]] = {
        "keyword_heavy": [1.0, 2.0],
        "vector_heavy": [2.0, 1.0],
        "balanced": [1.0, 1.0],
    }
    weights = strategy_weights.get(strategy)

    merged = rrf_merge(
        [vector_ranked, fts_ranked],
        k=settings.search_rrf_k,
        weights=weights,
    )
```

To:

```python
    strategy_config: dict[str, dict] = {
        "keyword_heavy": {"weights": [1.0, 2.0], "k": settings.search_rrf_k_keyword_heavy},
        "vector_heavy": {"weights": [2.0, 1.0], "k": settings.search_rrf_k_vector_heavy},
        "balanced": {"weights": [1.0, 1.0], "k": settings.search_rrf_k},
    }
    config = strategy_config.get(strategy, strategy_config["balanced"])

    merged = rrf_merge(
        [vector_ranked, fts_ranked],
        k=config["k"],
        weights=config["weights"],
    )
```

Also update the exact-match fallback (line 197) to use keyword_heavy k:

```python
    merged = rrf_merge([fts_ranked], k=settings.search_rrf_k_keyword_heavy)
```

**Step 6: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_hybrid_search.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add backend/app/core/config.py backend/app/core/search/hybrid.py backend/tests/unit/test_hybrid_search.py
git commit -m "feat(m6): per-strategy RRF k configuration for query tuning"
```

---

### Task 7: m7 — Add Explicit Confidence Field to Citation Dataclass

**Files:**
- Modify: `backend/app/core/legal/extractor.py:17-26` (Citation dataclass)
- Modify: `backend/app/core/legal/extractor.py:603-615` (name citation extraction)
- Test: `backend/tests/unit/test_extractor*.py`

**Context:** Citation confidence is currently implicit (`reporter="NameCitation"`, `year=0`, `page="0"`). Adding an explicit `confidence: float` field (0.0–1.0) makes downstream filtering clearer and self-documenting.

**Step 1: Write the failing test**

```python
def test_name_citation_has_low_confidence():
    """Name-based citations should have confidence < 0.5."""
    from app.core.legal.extractor import extract_citations

    text = "as held in Kesavananda Bharati v. State of Kerala"
    citations = extract_citations(text)
    name_cites = [c for c in citations if c.reporter == "NameCitation"]
    assert len(name_cites) >= 1
    assert all(c.confidence < 0.5 for c in name_cites)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_extractor_confidence.py -v`
Expected: FAIL — `Citation` has no `confidence` attribute

**Step 3: Add confidence field to Citation dataclass**

In `extractor.py`, modify the dataclass (lines 17-26):

```python
@dataclass(frozen=True)
class Citation:
    reporter: str
    year: int
    volume: str | None
    page: str
    court: str | None
    raw_text: str
    confidence: float = 1.0  # 0.0-1.0, default high for formal citations
```

**Step 4: Set confidence for each citation type**

- Neutral citations (YYYY:INSC:NNNN): `confidence=0.95`
- SCC/AIR/formal reporters: `confidence=0.9`
- MANU/other reporters: `confidence=0.8`
- Name-based citations: `confidence=0.3`

Update the `_add(Citation(...))` calls:
- Line ~603-615 (name citations): add `confidence=0.3`
- Other extraction functions: add appropriate confidence values

**Step 5: Run all extractor tests**

Run: `cd backend && python -m pytest tests/unit/ -k "extractor" -v`
Expected: All PASS (existing tests shouldn't break since `confidence` has a default)

**Step 6: Commit**

```bash
git add backend/app/core/legal/extractor.py backend/tests/unit/test_extractor_confidence.py
git commit -m "feat(m7): add explicit confidence field to Citation dataclass"
```

---

### Task 8: m8 — Async Retry Queue for Failed Graph Builds

**Files:**
- Create: `backend/app/core/ingestion/graph_retry.py`
- Modify: `backend/app/core/ingestion/pipeline.py:333-338`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/unit/test_graph_retry.py` (create)

**Context:** Graph build failures (Neo4j timeout, connection issues) are logged and silently swallowed. The case is marked "complete" but its citation graph is missing. We need a retry mechanism that records failed graph builds and retries them later.

**Step 1: Write the failing test for the retry recorder**

```python
"""Tests for graph build retry queue."""
from __future__ import annotations

from unittest.mock import AsyncMock
import pytest

from app.core.ingestion.graph_retry import record_graph_failure, get_pending_retries


@pytest.mark.asyncio
async def test_record_graph_failure_inserts_row():
    """Recording a graph failure should insert into graph_build_queue."""
    mock_db = AsyncMock()
    await record_graph_failure(mock_db, "case-123", "Connection timeout")
    mock_db.execute.assert_called_once()
    call_sql = str(mock_db.execute.call_args[0][0])
    assert "graph_build_queue" in call_sql.lower() or "graph_build_failures" in call_sql.lower()


@pytest.mark.asyncio
async def test_get_pending_retries_returns_failed_cases():
    """get_pending_retries should return cases that need graph rebuild."""
    mock_db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.fetchall.return_value = [
        ("case-1", 1),
        ("case-2", 0),
    ]
    mock_db.execute.return_value = mock_result
    pending = await get_pending_retries(mock_db, max_retries=3)
    assert len(pending) == 2
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_graph_retry.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Create the graph_retry module**

```python
"""Async retry queue for failed citation graph builds.

When Neo4j is temporarily unavailable during ingestion, the graph build
step fails but the case is still marked complete (graph is non-critical).
This module records those failures and provides a mechanism to retry them.
"""
from __future__ import annotations

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def record_graph_failure(
    db: AsyncSession,
    case_id: str,
    error: str,
) -> None:
    """Record a failed graph build for later retry."""
    await db.execute(
        text(
            "INSERT INTO graph_build_queue (case_id, error, retry_count, created_at) "
            "VALUES (:case_id, :error, 0, NOW()) "
            "ON CONFLICT (case_id) DO UPDATE SET "
            "error = :error, retry_count = graph_build_queue.retry_count, updated_at = NOW()"
        ),
        {"case_id": case_id, "error": error[:500]},
    )
    await db.commit()


async def get_pending_retries(
    db: AsyncSession,
    max_retries: int = 3,
) -> list[tuple[str, int]]:
    """Return (case_id, retry_count) pairs pending graph rebuild."""
    result = await db.execute(
        text(
            "SELECT case_id, retry_count FROM graph_build_queue "
            "WHERE retry_count < :max_retries "
            "ORDER BY created_at ASC"
        ),
        {"max_retries": max_retries},
    )
    return [(row[0], row[1]) for row in result.fetchall()]


async def mark_retry_success(db: AsyncSession, case_id: str) -> None:
    """Remove a case from the retry queue after successful graph build."""
    await db.execute(
        text("DELETE FROM graph_build_queue WHERE case_id = :case_id"),
        {"case_id": case_id},
    )
    await db.commit()


async def increment_retry_count(db: AsyncSession, case_id: str) -> None:
    """Increment retry count after a failed attempt."""
    await db.execute(
        text(
            "UPDATE graph_build_queue SET retry_count = retry_count + 1, "
            "updated_at = NOW() WHERE case_id = :case_id"
        ),
        {"case_id": case_id},
    )
    await db.commit()
```

**Step 4: Create the migration for graph_build_queue table**

Create `backend/migrations/versions/015_graph_build_queue.py`:

```python
"""Add graph_build_queue table for retry of failed citation graph builds."""

revision = "015"
down_revision = "014"

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "graph_build_queue",
        sa.Column("case_id", sa.String, sa.ForeignKey("cases.id"), primary_key=True),
        sa.Column("error", sa.String(500), nullable=False),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("graph_build_queue")
```

**Step 5: Wire into pipeline.py**

In `pipeline.py`, modify the graph failure handler (lines ~334-338):

```python
        except (Exception, asyncio.TimeoutError) as graph_exc:
            # Graph build is non-critical; log and queue for retry
            logger.error(
                "Citation graph build failed for case_id=%s: %s",
                case_id, graph_exc,
            )
            try:
                await record_graph_failure(db, case_id, str(graph_exc))
            except Exception as queue_exc:
                logger.error(
                    "Failed to queue graph retry for case_id=%s: %s",
                    case_id, queue_exc,
                )
```

Add the import at the top of pipeline.py:

```python
from app.core.ingestion.graph_retry import record_graph_failure
```

**Step 6: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_graph_retry.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add backend/app/core/ingestion/graph_retry.py backend/app/core/ingestion/pipeline.py backend/migrations/versions/015_graph_build_queue.py backend/tests/unit/test_graph_retry.py
git commit -m "feat(m8): async retry queue for failed citation graph builds"
```

---

### Task 9: m9 — Accept ingestion_tracker.db as Local-Only (No Change)

**Context:** `ingestion_tracker.db` at `config.py:83` is a local SQLite file used only by the ingestion CLI script for tracking download progress. It's not used in production Cloud Run. This is already appropriate for its use case.

**Action:** No code changes. Add a brief inline comment if one doesn't exist:

```python
    # Local-only SQLite for ingestion CLI job tracking (not used in Cloud Run)
    ingestion_tracker_db: str = "./data/ingestion_tracker.db"
```

**Commit:**

```bash
git add backend/app/core/config.py
git commit -m "docs(m9): clarify ingestion_tracker.db is local-only"
```

---

## Execution Order

Tasks are independent and can be parallelized. Suggested order by impact:

1. **Task 1 (m1)** — Transaction fix (data integrity)
2. **Task 8 (m8)** — Graph retry queue (data completeness)
3. **Task 4 (m4)** — Worker Dockerfile (deployment gap)
4. **Task 6 (m6)** — Per-strategy RRF k (search quality)
5. **Task 7 (m7)** — Citation confidence (code clarity)
6. **Task 3 (m3)** — Cloud Run concurrency (config)
7. **Task 2 (m2)** — Pinecone truncation log (observability)
8. **Task 5 (m5)** — ts_rank_cd ADR (documentation)
9. **Task 9 (m9)** — Accept + comment (trivial)

## Final Verification

After all tasks:

```bash
cd backend && python -m pytest tests/unit/ -v --tb=short
```

Expected: All 1411+ tests PASS (plus new tests from this plan).
