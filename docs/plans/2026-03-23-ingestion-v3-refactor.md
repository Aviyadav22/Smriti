# Ingestion Pipeline V3 — Proposition-Level Retrieval Refactor

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add legal proposition extraction, multi-vector-type Pinecone storage, section-aware chunking, and statute interpretation tables — closing the retrieval gap where Smriti currently finds the right case but not the right legal point.

**Architecture:** Three new LLM-extracted fields (`legal_propositions`, `statute_sections_interpreted`, `fact_pattern_summary`) feed three new Pinecone vector types (`proposition`, `ratio`, `headnote`) alongside existing `chunk` vectors. A `vector_type` metadata field distinguishes them. Retrieval workers query all types and merge via RRF with type-based boosts. A new `case_statute_interpretations` SQL table enables exact statute lookups.

**Tech Stack:** PostgreSQL (migration 035), Pinecone (same index, new metadata), Gemini 2.5 Pro/Flash (extraction), gemini-embedding-001 (1536-dim), LangGraph workers

**PRD:** `SMRITI_REFACTOR_PRD.md` (the user's ingestion refactor specification)

---

## Task 1: Add `source_dataset` column to cases table

Tag provenance of ingestion source for future HC expansion.

**Files:**
- Create: `backend/migrations/versions/035_ingestion_v3_fields.py`
- Modify: `backend/app/models/case.py`

**Step 1: Write the migration**

```python
# migrations/versions/035_ingestion_v3_fields.py
"""Ingestion V3: source_dataset, legal_propositions, statute_sections_interpreted, fact_pattern_summary, chunk_legal_signal"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "035"
down_revision = "034"

def upgrade() -> None:
    op.add_column("cases", sa.Column("source_dataset", sa.String(50), server_default="aws_open_data_sc"))
    op.add_column("cases", sa.Column("legal_propositions", JSONB, nullable=True))
    op.add_column("cases", sa.Column("statute_sections_interpreted", JSONB, nullable=True))
    op.add_column("cases", sa.Column("fact_pattern_summary", sa.Text, nullable=True))
    op.create_index("ix_cases_source_dataset", "cases", ["source_dataset"])

def downgrade() -> None:
    op.drop_index("ix_cases_source_dataset")
    op.drop_column("cases", "fact_pattern_summary")
    op.drop_column("cases", "statute_sections_interpreted")
    op.drop_column("cases", "legal_propositions")
    op.drop_column("cases", "source_dataset")
```

**Step 2: Add columns to SQLAlchemy model**

In `backend/app/models/case.py`, add after `enrichment_status` (around line 230):

```python
    # --- Ingestion V3 fields ---
    source_dataset: Mapped[str | None] = mapped_column(
        String(50), server_default="aws_open_data_sc", index=True
    )
    legal_propositions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    statute_sections_interpreted: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fact_pattern_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Step 3: Run migration**

```bash
cd backend && alembic upgrade head
```

**Step 4: Commit**

```bash
git add migrations/versions/035_ingestion_v3_fields.py backend/app/models/case.py
git commit -m "feat(ingestion): add V3 schema — source_dataset, legal_propositions, statute interpretation, fact_pattern_summary"
```

---

## Task 2: Create `case_statute_interpretations` table

Exact statute lookup table — "find all cases interpreting Section 20(c) CPC" as a SQL query.

**Files:**
- Modify: `backend/migrations/versions/035_ingestion_v3_fields.py` (add to same migration)
- Create: `backend/app/models/case_statute_interpretation.py`

**Step 1: Add table creation to migration**

Append to the `upgrade()` function in migration 035:

```python
    op.create_table(
        "case_statute_interpretations",
        sa.Column("id", sa.dialects.postgresql.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", sa.dialects.postgresql.UUID, sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_text", sa.String(200), nullable=False),
        sa.Column("normalized_section", sa.String(200), nullable=False),
        sa.Column("act_name", sa.String(200), nullable=False),
        sa.Column("interpretation_summary", sa.Text, nullable=True),
        sa.Column("is_primary_holding", sa.Boolean, server_default="false"),
        sa.UniqueConstraint("case_id", "normalized_section", name="uq_case_statute_interp"),
    )
    op.create_index("ix_csi_normalized_section", "case_statute_interpretations", ["normalized_section"])
    op.create_index("ix_csi_case_id", "case_statute_interpretations", ["case_id"])
    op.create_index("ix_csi_act_name", "case_statute_interpretations", ["act_name"])
```

Add to `downgrade()`:

```python
    op.drop_table("case_statute_interpretations")
```

**Step 2: Create SQLAlchemy model**

```python
# backend/app/models/case_statute_interpretation.py
"""Model for case-statute interpretation cross-reference."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class CaseStatuteInterpretation(UUIDPrimaryKeyMixin, Base):
    """Records which statutory provisions a case substantively interprets."""

    __tablename__ = "case_statute_interpretations"
    __table_args__ = (
        UniqueConstraint("case_id", "normalized_section", name="uq_case_statute_interp"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_text: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_section: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    act_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    interpretation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary_holding: Mapped[bool] = mapped_column(Boolean, server_default="false")
```

**Step 3: Register model in `__init__.py`**

In `backend/app/models/__init__.py`, add:
```python
from app.models.case_statute_interpretation import CaseStatuteInterpretation  # noqa: F401
```

**Step 4: Commit**

```bash
git add backend/migrations/versions/035_ingestion_v3_fields.py backend/app/models/case_statute_interpretation.py backend/app/models/__init__.py
git commit -m "feat(ingestion): case_statute_interpretations table for exact statute lookup"
```

---

## Task 3: Add V3 extraction fields to CaseMetadata + LLM prompts

The three highest-impact new fields: `legal_propositions`, `statute_sections_interpreted`, `fact_pattern_summary`.

**Files:**
- Modify: `backend/app/core/ingestion/metadata.py:83-154` (CaseMetadata dataclass)
- Modify: `backend/app/core/legal/prompts.py` (METADATA_EXTRACTION_SYSTEM, METADATA_EXTRACTION_USER, METADATA_OUTPUT_SCHEMA)
- Modify: `backend/app/core/ingestion/metadata.py:743-762` (merge_metadata LLM-only fields)

**Step 1: Add fields to CaseMetadata**

In `metadata.py`, after `enrichment_status` (line 154), add:

```python
    # --- Ingestion V3 fields ---
    source_dataset: str = "aws_open_data_sc"
    legal_propositions: list[dict] | None = None  # [{proposition_text, paragraph_number, is_novel, related_section}]
    statute_sections_interpreted: list[dict] | None = None  # [{section, act, interpretation_summary}]
    fact_pattern_summary: str | None = None
```

**Step 2: Add extraction rules to METADATA_EXTRACTION_SYSTEM**

In `prompts.py`, after Rule 30 (around line 124), add:

```python
Rule 31: LEGAL PROPOSITIONS: Extract 3-10 discrete legal propositions established or \
affirmed by this judgment. Each proposition should be a single, self-contained statement \
of law that a lawyer could cite this case for. Do NOT restate the facts — state the \
abstract legal rule. Format: list of objects with keys: proposition_text (the legal \
statement), paragraph_number (the paragraph where this proposition appears, or null), \
is_novel (true if this case ESTABLISHES the proposition for the first time, false if it \
AFFIRMS existing law), related_section (the statute section this proposition interprets, \
if any, e.g. "Section 138, Indian Evidence Act, 1872", or null). \
Example proposition: "Cross-examination under Section 138 of the Evidence Act is the \
examination of a witness by the adverse party, and does not extend to co-accused inter se."

Rule 32: STATUTE SECTIONS INTERPRETED: Different from acts_cited. List ONLY the \
statutory provisions that this judgment SUBSTANTIVELY interprets, applies, or rules upon. \
Do NOT include sections merely referenced in passing or cited for general context. \
Format: list of objects with keys: section (e.g. "Section 20(c)"), act (e.g. "Code of \
Civil Procedure, 1908"), interpretation_summary (1 sentence summarizing what the court \
held about this section). Maximum 10 entries.

Rule 33: FACT PATTERN SUMMARY: In 2-3 sentences, describe the factual scenario of this \
case in GENERIC terms suitable for analogical matching. Strip party names and use role \
descriptions instead (e.g., "employer" not "Tata Motors", "accused" not "Rajesh Kumar"). \
Focus on the factual pattern that makes this case a useful precedent. Example: "An \
employee was terminated after 15 years of service for alleged misconduct without being \
given an opportunity to present their defense in a departmental inquiry."
```

**Step 3: Add fields to METADATA_EXTRACTION_USER prompt**

In the user prompt section (around line 130-140), add these fields to the requested JSON structure:

```python
    "legal_propositions": [
        {
            "proposition_text": "string — self-contained legal statement",
            "paragraph_number": "integer or null",
            "is_novel": "boolean — true if case establishes this, false if affirms",
            "related_section": "string or null — e.g. 'Section 302, IPC, 1860'"
        }
    ],
    "statute_sections_interpreted": [
        {
            "section": "string — e.g. 'Section 20(c)'",
            "act": "string — e.g. 'Code of Civil Procedure, 1908'",
            "interpretation_summary": "string — 1 sentence"
        }
    ],
    "fact_pattern_summary": "string — 2-3 sentences, generic fact pattern, no party names",
```

**Step 4: Add to METADATA_OUTPUT_SCHEMA**

Add these properties to the JSON schema:

```python
        "legal_propositions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "proposition_text": {"type": "string"},
                    "paragraph_number": {"type": "integer", "nullable": True},
                    "is_novel": {"type": "boolean"},
                    "related_section": {"type": "string", "nullable": True},
                },
                "required": ["proposition_text", "is_novel"],
            },
            "nullable": True,
        },
        "statute_sections_interpreted": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "act": {"type": "string"},
                    "interpretation_summary": {"type": "string"},
                },
                "required": ["section", "act"],
            },
            "nullable": True,
        },
        "fact_pattern_summary": {"type": "string", "nullable": True},
```

**Step 5: Add to merge_metadata LLM-only fields**

In `metadata.py` merge_metadata function (~line 743-762), add to the LLM-only field list:

```python
    "legal_propositions", "statute_sections_interpreted", "fact_pattern_summary",
```

**Step 6: Run existing tests**

```bash
cd backend && python -m pytest tests/unit/test_metadata.py tests/unit/test_metadata_v2.py -x -q
```

**Step 7: Commit**

```bash
git add backend/app/core/ingestion/metadata.py backend/app/core/legal/prompts.py
git commit -m "feat(ingestion): V3 extraction — legal_propositions, statute_sections_interpreted, fact_pattern_summary"
```

---

## Task 4: Add cross-validation — propositions ↔ ratio_decidendi

If ratio is empty but propositions exist, synthesize. If propositions empty but ratio exists, flag.

**Files:**
- Modify: `backend/app/core/ingestion/metadata.py` (add `_cross_validate_propositions` function)
- Modify: `backend/app/core/ingestion/pipeline.py` (call after merge)

**Step 1: Write the cross-validation function**

In `metadata.py`, after `compute_extraction_confidence()`:

```python
def cross_validate_propositions(metadata: CaseMetadata) -> CaseMetadata:
    """Cross-reference legal_propositions against ratio_decidendi.

    - If ratio is empty but propositions exist, synthesize ratio from top 3.
    - If propositions empty but ratio exists, create a single proposition from ratio.
    """
    props = metadata.legal_propositions or []
    ratio = metadata.ratio_decidendi or ""

    if not ratio.strip() and props:
        # Synthesize ratio from top propositions (non-novel first, then novel)
        sorted_props = sorted(props, key=lambda p: (p.get("is_novel", False),))
        top = sorted_props[:3]
        metadata.ratio_decidendi = " ".join(p["proposition_text"] for p in top)

    if ratio.strip() and not props:
        # Create a single proposition from ratio
        metadata.legal_propositions = [{
            "proposition_text": ratio.strip(),
            "paragraph_number": None,
            "is_novel": False,
            "related_section": None,
        }]

    return metadata
```

**Step 2: Call from pipeline**

In `pipeline.py`, after the metadata merge + regex validation (around line 230), add:

```python
    metadata = cross_validate_propositions(metadata)
```

Import at top of `pipeline.py`:
```python
from app.core.ingestion.metadata import cross_validate_propositions
```

**Step 3: Write test**

```python
# In tests/unit/test_metadata.py — add these test functions

def test_cross_validate_synthesizes_ratio_from_propositions():
    from app.core.ingestion.metadata import CaseMetadata, cross_validate_propositions
    meta = CaseMetadata(
        legal_propositions=[
            {"proposition_text": "Section 302 requires mens rea.", "is_novel": False},
            {"proposition_text": "Circumstantial evidence must be conclusive.", "is_novel": True},
        ],
        ratio_decidendi=None,
    )
    result = cross_validate_propositions(meta)
    assert "Section 302" in result.ratio_decidendi
    assert "mens rea" in result.ratio_decidendi

def test_cross_validate_creates_proposition_from_ratio():
    from app.core.ingestion.metadata import CaseMetadata, cross_validate_propositions
    meta = CaseMetadata(
        ratio_decidendi="The right to privacy is a fundamental right under Article 21.",
        legal_propositions=None,
    )
    result = cross_validate_propositions(meta)
    assert len(result.legal_propositions) == 1
    assert "privacy" in result.legal_propositions[0]["proposition_text"]
```

**Step 4: Run tests**

```bash
cd backend && python -m pytest tests/unit/test_metadata.py -x -q
```

**Step 5: Commit**

```bash
git add backend/app/core/ingestion/metadata.py backend/app/core/ingestion/pipeline.py tests/unit/test_metadata.py
git commit -m "feat(ingestion): cross-validate propositions ↔ ratio_decidendi"
```

---

## Task 5: Section-aware chunk sizing — smaller chunks for ANALYSIS/RATIO/ORDER

Dense legal sections get 1200-char chunks (more focused embeddings), narrative sections keep 2000.

**Files:**
- Modify: `backend/app/core/ingestion/chunker.py:257-258` (chunk size constants)
- Modify: `backend/app/core/ingestion/chunker.py:449-514` (chunking logic)
- Modify: `backend/tests/unit/test_chunker.py`

**Step 1: Add section-aware constants**

In `chunker.py`, replace lines 257-258:

```python
# OLD
CHUNK_SIZE: int = 2000
CHUNK_OVERLAP: int = 200

# NEW
CHUNK_SIZE: int = 2000
CHUNK_OVERLAP: int = 200
# Dense legal sections get smaller, more focused chunks
_DENSE_SECTIONS: frozenset[str] = frozenset({"ANALYSIS", "RATIO", "ORDER", "DISSENT", "CONCURRENCE"})
_DENSE_CHUNK_SIZE: int = 1200
_DENSE_CHUNK_OVERLAP: int = 300
```

**Step 2: Use section-aware sizes in chunking loop**

In `chunk_judgment()`, in the loop over sections (around line 449), change the chunk_size/overlap selection:

```python
        # Section-aware chunk sizing
        effective_chunk_size = _DENSE_CHUNK_SIZE if sec.type in _DENSE_SECTIONS else CHUNK_SIZE
        effective_overlap = _DENSE_CHUNK_OVERLAP if sec.type in _DENSE_SECTIONS else CHUNK_OVERLAP
```

Then replace all references to `CHUNK_SIZE` and `CHUNK_OVERLAP` within the loop with `effective_chunk_size` and `effective_overlap`.

**Step 3: Write test**

```python
def test_dense_sections_get_smaller_chunks():
    from app.core.ingestion.chunker import chunk_judgment, Section
    # Create a long ANALYSIS section (3000 chars)
    analysis_text = "The court held that " * 150  # ~3000 chars
    sections = [Section(type="ANALYSIS", start=0, end=len(analysis_text), text=analysis_text)]
    chunks = chunk_judgment(analysis_text, sections, case_id="test")
    # With 1200-char chunks, should produce 3+ chunks (not 2 as with 2000-char)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk.text) <= 1200 + 50  # small tolerance for break-point adjustment
```

**Step 4: Run tests**

```bash
cd backend && python -m pytest tests/unit/test_chunker.py -x -q
```

**Step 5: Commit**

```bash
git add backend/app/core/ingestion/chunker.py tests/unit/test_chunker.py
git commit -m "feat(ingestion): section-aware chunk sizing — 1200 chars for ANALYSIS/RATIO/ORDER"
```

---

## Task 6: Add `chunk_legal_signal` score

Fast heuristic scoring of how likely a chunk contains holdings vs narrative.

**Files:**
- Modify: `backend/app/core/ingestion/chunker.py` (add scoring function + Chunk field)

**Step 1: Add field to Chunk dataclass**

In `chunker.py`, modify the `Chunk` dataclass (line 27-38):

```python
@dataclass(frozen=True, slots=True)
class Chunk:
    text: str
    section_type: str
    chunk_index: int
    case_id: str
    page_number: int | None = None
    para_start: int | None = None
    para_end: int | None = None
    opinion_author: str | None = None
    legal_signal: float = 0.0  # V3: signal phrase density (higher = more likely a holding)
```

**Step 2: Add scoring function**

After the Chunk dataclass:

```python
_LEGAL_SIGNAL_PHRASES: tuple[str, ...] = (
    "held that", "we hold", "in our opinion", "it is well settled",
    "the ratio", "we are of the view", "the principle",
    "we approve", "we overrule", "we distinguish",
    "the question is answered", "the appeal is allowed",
    "the appeal is dismissed", "we are of the considered view",
    "in our considered opinion", "we accordingly hold",
)

def _compute_legal_signal(text: str) -> float:
    """Compute legal signal density: count of signal phrases per 1000 chars."""
    if not text:
        return 0.0
    text_lower = text.lower()
    count = sum(1 for phrase in _LEGAL_SIGNAL_PHRASES if phrase in text_lower)
    return round(count / len(text) * 1000, 2)
```

**Step 3: Call scoring during chunk creation**

In `chunk_judgment()`, where chunks are created (around line 465), pass the score:

```python
    # After creating chunk text, compute legal signal
    signal = _compute_legal_signal(chunk_text)
    chunks.append(Chunk(
        text=chunk_text,
        section_type=sec.type,
        chunk_index=global_index,
        case_id=case_id,
        para_start=para_range[0] if para_range else None,
        para_end=para_range[1] if para_range else None,
        opinion_author=current_author,
        legal_signal=signal,
    ))
```

**Step 4: Write test**

```python
def test_legal_signal_scoring():
    from app.core.ingestion.chunker import _compute_legal_signal
    high = _compute_legal_signal("We held that the appeal is dismissed. In our opinion, the principle is well settled.")
    low = _compute_legal_signal("The petitioner filed a complaint on 15th March 2020 regarding the property dispute.")
    assert high > low
    assert high > 0
```

**Step 5: Run tests, commit**

```bash
cd backend && python -m pytest tests/unit/test_chunker.py -x -q
git add backend/app/core/ingestion/chunker.py tests/unit/test_chunker.py
git commit -m "feat(ingestion): chunk_legal_signal score for retrieval boosting"
```

---

## Task 7: Improve contextual embedding prompt

Make the context prefix retrieval-oriented, not just structural.

**Files:**
- Modify: `backend/app/core/ingestion/contextual_embeddings.py:22-30` (CONTEXTUAL_PREFIX_SYSTEM)

**Step 1: Replace the system prompt**

In `contextual_embeddings.py`, replace `CONTEXTUAL_PREFIX_SYSTEM` (lines 22-30):

```python
CONTEXTUAL_PREFIX_SYSTEM: str = """\
You are a legal document analyst. Given a chunk from an Indian court judgment and \
metadata about the full document, generate a concise 1-2 sentence context prefix that \
states:
(1) What specific legal question this chunk addresses.
(2) What the court's position is on that question (if discernible from the chunk).
If the chunk is purely factual narration, state what legal issue the facts relate to.
Include the case citation.

Format: "<context prefix>\\n\\n<original chunk text>"
Do NOT summarize or paraphrase the chunk. Only add contextual framing.\
"""
```

**Step 2: Commit**

```bash
git add backend/app/core/ingestion/contextual_embeddings.py
git commit -m "feat(ingestion): retrieval-oriented contextual embedding prompt"
```

---

## Task 8: Multi-vector Pinecone upsert — proposition, ratio, headnote vectors

This is the highest-impact retrieval change. Add three new vector types alongside existing chunk vectors.

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py` (`_upsert_vectors` function + new helper)

**Step 1: Add `vector_type` to existing chunk vector metadata**

In `_upsert_vectors()` (around line 974-1006), add to the metadata dict:

```python
    "vector_type": "chunk",
```

This tags all existing vectors. Non-breaking — existing search will still work.

**Step 2: Add proposition/ratio/headnote vector creation**

Add a new function after `_upsert_vectors()`:

```python
async def _upsert_proposition_vectors(
    case_id: str,
    metadata: CaseMetadata,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    *,
    rate_limiter: AsyncRateLimiter | None = None,
) -> int:
    """Create separate Pinecone vectors for propositions, ratio, and headnotes.

    Returns the total number of vectors upserted.
    """
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

    # --- Proposition vectors ---
    for i, prop in enumerate(metadata.legal_propositions or []):
        prop_text = prop.get("proposition_text", "")
        if not prop_text or len(prop_text) < 20:
            continue
        vid = f"{case_id}_prop_{i}"
        vector_ids.append(vid)
        texts_to_embed.append(prop_text)
        vectors.append({
            "id": vid,
            "metadata": {
                **base_meta,
                "vector_type": "proposition",
                "text": prop_text[:2000],
                "section_type": "RATIO",
                "related_section": prop.get("related_section") or "",
                "is_novel": prop.get("is_novel", False),
                "para_start": prop.get("paragraph_number") or 0,
                "para_end": prop.get("paragraph_number") or 0,
            },
        })

    # --- Ratio vector (one per case) ---
    ratio = metadata.ratio_decidendi or ""
    if len(ratio.strip()) >= 30:
        vid = f"{case_id}_ratio"
        vector_ids.append(vid)
        texts_to_embed.append(ratio)
        vectors.append({
            "id": vid,
            "metadata": {
                **base_meta,
                "vector_type": "ratio",
                "text": ratio[:2000],
                "section_type": "RATIO",
            },
        })

    # --- Headnote vectors ---
    # headnotes is stored as a JSON string in CaseMetadata
    headnotes_raw = metadata.headnotes or ""
    headnotes: list[dict] = []
    if headnotes_raw:
        try:
            headnotes = json.loads(headnotes_raw) if isinstance(headnotes_raw, str) else headnotes_raw
        except (ValueError, TypeError):
            headnotes = []
    for i, hn in enumerate(headnotes):
        hn_text = hn.get("proposition", "") if isinstance(hn, dict) else str(hn)
        if not hn_text or len(hn_text) < 20:
            continue
        vid = f"{case_id}_headnote_{i}"
        vector_ids.append(vid)
        texts_to_embed.append(hn_text)
        vectors.append({
            "id": vid,
            "metadata": {
                **base_meta,
                "vector_type": "headnote",
                "text": hn_text[:2000],
                "section_type": "RATIO",
            },
        })

    if not texts_to_embed:
        return 0

    # Embed all at once
    embeddings = await _embed_chunks(
        [],  # unused — we pass texts_override
        embedder,
        rate_limiter=rate_limiter,
        texts_override=texts_to_embed,
    )

    # Attach embeddings to vectors
    for vec, emb in zip(vectors, embeddings):
        vec["values"] = emb

    # Upsert in batches of 100
    for batch_start in range(0, len(vectors), _EMBED_BATCH_SIZE):
        batch = vectors[batch_start : batch_start + _EMBED_BATCH_SIZE]
        await vector_store.upsert(batch)

    logger.info("Upserted %d proposition/ratio/headnote vectors for %s", len(vectors), case_id)
    return len(vectors)
```

**Step 3: Call from ingest_judgment AND fix stale vector cleanup**

In `ingest_judgment()`, after the main `_upsert_vectors()` call (around line 414), add:

```python
    # V3: Proposition-level vectors for direct legal-point retrieval
    prop_vector_ids: list[str] = []
    try:
        prop_count, prop_vector_ids = await _upsert_proposition_vectors(
            case_id, metadata, embedder, vector_store,
            rate_limiter=embed_rate_limiter,
        )
        if prop_count:
            logger.info("Created %d proposition vectors for %s", prop_count, case_id)
    except Exception as exc:
        logger.warning("Proposition vector upsert failed for %s: %s", case_id, exc)
        if warnings_out is not None:
            warnings_out.append(f"proposition_vectors_failed: {exc}")
```

**CRITICAL: Fix stale vector cleanup** — At line 378-380 where `new_vector_ids` is built, ALSO include proposition vector IDs:

```python
    new_vector_ids = [
        f"{case_id}_{chunk.chunk_index}" for chunk in chunks
    ]
    # After proposition upsert, extend with proposition IDs
    new_vector_ids.extend(prop_vector_ids)
```

The `_upsert_proposition_vectors` function should return `(count, vector_ids)` instead of just `count`:

```python
    # At the end of _upsert_proposition_vectors:
    return len(vectors), vector_ids
```

**Step 4: Store V3 fields in PostgreSQL INSERT**

In `_insert_case()` SQL INSERT (around line 728-774), add these columns:

```sql
    legal_propositions, statute_sections_interpreted, fact_pattern_summary, source_dataset
```

And corresponding values:

```python
    "legal_propositions": json.dumps(metadata.legal_propositions) if metadata.legal_propositions else None,
    "statute_sections_interpreted": json.dumps(metadata.statute_sections_interpreted) if metadata.statute_sections_interpreted else None,
    "fact_pattern_summary": metadata.fact_pattern_summary,
    "source_dataset": metadata.source_dataset if hasattr(metadata, "source_dataset") else "aws_open_data_sc",
```

**Step 5: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py
git commit -m "feat(ingestion): multi-vector Pinecone — proposition, ratio, headnote vectors + V3 field storage"
```

---

## Task 9: Persist statute interpretations to SQL table

After metadata extraction, populate the `case_statute_interpretations` table.

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py` (add `_persist_statute_interpretations`)

**Step 1: Add persistence function**

```python
async def _persist_statute_interpretations(
    case_id: str,
    metadata: CaseMetadata,
    db: AsyncSession,
) -> None:
    """Populate case_statute_interpretations from metadata.statute_sections_interpreted."""
    interpretations = metadata.statute_sections_interpreted or []
    if not interpretations:
        return

    from app.core.legal.extractor import normalize_act_name

    for interp in interpretations[:10]:  # Cap at 10
        section = interp.get("section", "").strip()
        act = interp.get("act", "").strip()
        if not section or not act:
            continue
        normalized = f"{section} {normalize_act_name(act)}".strip()
        await db.execute(
            text("""
                INSERT INTO case_statute_interpretations
                    (id, case_id, section_text, normalized_section, act_name,
                     interpretation_summary, is_primary_holding)
                VALUES (gen_random_uuid(), :case_id, :section_text, :normalized,
                        :act_name, :summary, :is_primary)
                ON CONFLICT (case_id, normalized_section) DO UPDATE SET
                    interpretation_summary = EXCLUDED.interpretation_summary
            """),
            {
                "case_id": case_id,
                "section_text": f"{section} of {act}",
                "normalized": normalized,
                "act_name": act,
                "summary": interp.get("interpretation_summary", ""),
                "is_primary": False,
            },
        )
```

**Step 2: Call from ingest_judgment**

After `_persist_sections()` call (around line 314), add:

```python
    await _persist_statute_interpretations(case_id, metadata, db)
```

**Step 3: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py
git commit -m "feat(ingestion): persist statute interpretations to SQL lookup table"
```

---

## Task 10: Update retrieval workers to search across vector types

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py` (case_law_worker)
- Modify: `backend/app/core/search/hybrid.py` (add vector_type filter support)

**Step 1: Add vector_type to Pinecone filter building**

In `hybrid.py`, in the filter-building logic (around line 437-467), add support for `vector_type`:

```python
    # Default to chunk vectors for backward compatibility
    if hasattr(filters, "vector_types") and filters.vector_types:
        pinecone_filter["vector_type"] = {"$in": filters.vector_types}
```

**Step 2: Add SearchFilters field**

In the `SearchFilters` dataclass/class, add:
```python
    vector_types: list[str] | None = None  # ["chunk", "proposition", "ratio", "headnote"]
```

**Step 3: Semantic-only proposition search in case_law_worker**

In `worker_nodes.py` case_law_worker, after the main search, add a **semantic-only** proposition search.

NOTE: Do NOT use `parallel_hybrid_search` for proposition vectors — the FTS (boolean) side searches PostgreSQL `searchable_text` which contains full judgment text, NOT proposition text. Using hybrid search would dilute precision by mixing proposition-level Pinecone results with chunk-level FTS results. Instead, search Pinecone directly:

```python
    # V3: Proposition-level semantic search (skip FTS — propositions are vector-only)
    try:
        query_embedding = await embedder.embed_text(nl_query)
        prop_pinecone_results = await vector_store.search(
            query_embedding,
            top_k=10,
            filters={
                "vector_type": {"$in": ["proposition", "ratio"]},
                **({"court": {"$eq": search_filters.court[0]}} if search_filters and search_filters.court else {}),
                **({"year": {"$gte": search_filters.year_from}} if search_filters and search_filters.year_from else {}),
                **({"year": {"$lte": search_filters.year_to}} if search_filters and search_filters.year_to else {}),
            },
        )
        # Boost proposition results by 1.5x before merge
        for r in prop_pinecone_results:
            r.score = r.score * 1.5
            r.metadata["source"] = "proposition_search"
        all_results.extend(prop_pinecone_results)
    except Exception as exc:
        logger.warning("Proposition search failed (non-fatal): %s", exc)
```

**Step 4: Commit**

```bash
git add backend/app/core/agents/nodes/worker_nodes.py backend/app/core/search/hybrid.py
git commit -m "feat(retrieval): multi-vector search — proposition/ratio vectors with 1.5x boost"
```

---

## Task 11: Add `chunk_legal_signal` to Pinecone metadata

Store the legal signal score as a retrieval boost hint.

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py` (`_upsert_vectors` metadata dict)

**Step 1: Add to Pinecone metadata**

In `_upsert_vectors()`, in the metadata dict (around line 974-1006), add:

```python
    "legal_signal": chunk.legal_signal if hasattr(chunk, "legal_signal") else 0.0,
```

**Step 2: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py
git commit -m "feat(ingestion): store chunk_legal_signal in Pinecone metadata"
```

---

## Task 12: Add Neo4j fulltext index on LegalPrinciple nodes

Enables graph-based retrieval of legal principles.

**Files:**
- Modify: `backend/app/core/providers/graph/neo4j_store.py` (`ensure_constraints`)

**Step 1: Add fulltext index**

In `ensure_constraints()` (around line 260), add:

```python
            await session.run(
                "CREATE FULLTEXT INDEX principle_text IF NOT EXISTS "
                "FOR (n:LegalPrinciple) ON EACH [n.name]"
            )
```

**Step 2: Commit**

```bash
git add backend/app/core/providers/graph/neo4j_store.py
git commit -m "feat(graph): fulltext index on LegalPrinciple nodes for graph retrieval"
```

---

## Task 13: Improve PDF extraction — per-page alpha ratio OCR fallback

Catch partially corrupted pages that pass the 30-char threshold but have garbled text.

**Files:**
- Modify: `backend/app/core/ingestion/pdf.py` (page extraction logic)

**Step 1: Add alpha ratio check**

After pdfplumber extraction per page, if char count > 30 but alpha ratio < 0.5, also run OCR and take the better result:

```python
    # After pdfplumber extraction:
    if page_text and len(page_text) > 30:
        alpha_count = sum(1 for c in page_text if c.isalpha())
        alpha_ratio = alpha_count / len(page_text) if page_text else 0
        if alpha_ratio < 0.5:
            # Garbled text — try OCR as well
            ocr_text = await extract_with_ocr(pdf_path, page_number=page_num)
            if ocr_text and len(ocr_text) > len(page_text):
                ocr_alpha = sum(1 for c in ocr_text if c.isalpha()) / len(ocr_text) if ocr_text else 0
                if ocr_alpha > alpha_ratio:
                    page_text = ocr_text
```

**Step 2: Commit**

```bash
git add backend/app/core/ingestion/pdf.py
git commit -m "feat(ingestion): alpha-ratio OCR fallback for garbled page detection"
```

---

## Task 14: Run full test suite + verify migration

**Step 1: Run migration**

```bash
cd backend && alembic upgrade head
```

**Step 2: Run all ingestion tests**

```bash
cd backend && python -m pytest tests/unit/test_ingestion_pipeline.py tests/unit/test_metadata.py tests/unit/test_chunker.py tests/unit/test_extractor.py -x -q
```

**Step 3: Run full backend suite**

```bash
cd backend && python -m pytest tests/ -x -q --ignore=tests/quality --ignore=tests/integration
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(ingestion): V3 refactor complete — proposition vectors, statute interpretations, section-aware chunking"
```

---

## Summary of Impact

| Change | Files | Impact |
|--------|-------|--------|
| `legal_propositions` extraction | prompts.py, metadata.py | **Highest** — direct legal-point retrieval |
| Proposition/ratio/headnote vectors | pipeline.py | **Highest** — 3 new vector types in Pinecone |
| `case_statute_interpretations` table | migration, model, pipeline | **High** — exact statute lookup |
| Section-aware chunking (1200 for ANALYSIS) | chunker.py | **Medium** — focused embeddings |
| `chunk_legal_signal` score | chunker.py, pipeline.py | **Medium** — retrieval boost signal |
| Multi-vector search in workers | worker_nodes.py, hybrid.py | **High** — searches propositions+ratio |
| Contextual embedding prompt | contextual_embeddings.py | **Medium** — better embedding quality |
| Alpha-ratio OCR fallback | pdf.py | **Low** — marginal text quality |
| `source_dataset` column | migration, model | **Low** — future-proofing |
| LegalPrinciple fulltext index | neo4j_store.py | **Low** — graph retrieval path |

**Two changes that matter most:** Extracting `legal_propositions` (Task 3) and embedding them as separate vectors (Task 8).
