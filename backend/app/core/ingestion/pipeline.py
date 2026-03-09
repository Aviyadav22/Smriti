"""Ingestion pipeline orchestrator for Indian court judgments.

Coordinates the full pipeline: PDF → text → metadata → chunks → embeddings → store.
Follows the architecture defined in DATA_SOURCES.md §3.

Also provides batch/bulk database helpers for high-throughput ingestion of
pre-processed judgments (bulk_upsert_cases, bulk_insert_sections,
bulk_insert_citations, ingest_batch).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion.chunker import Chunk, chunk_judgment, detect_judgment_sections
from app.core.ingestion.metadata import (
    CaseMetadata,
    extract_metadata_llm,
    merge_metadata,
    validate_cross_fields,
    validate_with_regex,
)
from app.core.ingestion.pdf import extract_and_score, extract_pdf_text, extract_with_ocr
from app.core.ingestion.rate_limiter import AsyncRateLimiter
from app.core.interfaces.embedder import EmbeddingProvider
from app.core.interfaces.graph_store import GraphStore
from app.core.interfaces.llm import LLMProvider
from app.core.interfaces.storage import FileStorage
from app.core.interfaces.vector_store import VectorStore
from app.core.legal.extractor import extract_citations

logger = logging.getLogger(__name__)

# Batch size for embedding calls to avoid overloading the API.
_EMBED_BATCH_SIZE: int = 20


async def ingest_judgment(
    pdf_path: str,
    parquet_metadata: dict,
    *,
    db: AsyncSession,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    graph_store: GraphStore,
    storage: FileStorage,
    rate_limiter: AsyncRateLimiter | None = None,
) -> str:
    """Full ingestion pipeline for a single Indian court judgment.

    Steps:
    1. Extract text from PDF (pdfplumber, OCR fallback)
    2. Extract + merge metadata (Parquet ground truth + LLM structured output)
    3. Validate metadata with regex sanity checks
    4. Store PDF to configured storage backend
    5. Insert case record into PostgreSQL
    6. Detect judgment sections and chunk text
    7. Generate embeddings for all chunks
    8. Upsert vectors to Pinecone
    9. Build citation graph edges in Neo4j

    Args:
        pdf_path: Path to the PDF file on disk.
        parquet_metadata: Dictionary of metadata from the Parquet file.
        db: Async SQLAlchemy session.
        llm: LLM provider for metadata extraction.
        embedder: Embedding provider for chunk vectorization.
        vector_store: Vector DB for similarity search.
        graph_store: Graph DB for citation network.
        storage: File storage for PDF archival.
        rate_limiter: Optional rate limiter to throttle Gemini API calls.

    Returns:
        The case UUID as a string.
    """
    case_id = str(uuid.uuid4())
    logger.info("Starting ingestion for case_id=%s, pdf=%s", case_id, pdf_path)

    # ------------------------------------------------------------------
    # 1. EXTRACT TEXT + QUALITY SCORING
    # ------------------------------------------------------------------
    quality = await extract_and_score(pdf_path)
    full_text = quality.text

    if not full_text or quality.char_count < 50:
        logger.error("No text extracted from PDF: %s", pdf_path)
        await _record_ingestion_failure(db, case_id, pdf_path, "No text extracted")
        return case_id

    if quality.tier == "low":
        logger.warning(
            "Low quality text for %s: %d chars, %d legal keywords (proceeding anyway)",
            pdf_path, quality.char_count, quality.legal_keyword_count,
        )

    # ------------------------------------------------------------------
    # 2. MERGE METADATA (Parquet + LLM)
    # ------------------------------------------------------------------
    if rate_limiter:
        await rate_limiter.acquire()
    llm_meta = await extract_metadata_llm(full_text, llm)
    metadata = merge_metadata(parquet_metadata, llm_meta)

    # ------------------------------------------------------------------
    # 3. VALIDATE METADATA
    # ------------------------------------------------------------------
    metadata = validate_with_regex(metadata)
    metadata = validate_cross_fields(metadata)

    # ------------------------------------------------------------------
    # 4. STORE PDF
    # ------------------------------------------------------------------
    storage_dest = f"cases/{case_id}/{_safe_filename(parquet_metadata)}"
    try:
        storage_path = await storage.store(pdf_path, storage_dest)
    except (OSError, PermissionError, FileNotFoundError) as exc:
        logger.error("Failed to store PDF %s: %s", pdf_path, exc)
        storage_path = pdf_path  # fallback: keep original path

    # ------------------------------------------------------------------
    # 5. INSERT CASE INTO POSTGRESQL (upsert on citation conflict)
    # ------------------------------------------------------------------
    case_id = await _insert_case(db, case_id, metadata, full_text, storage_path, parquet_metadata)

    try:
        # ------------------------------------------------------------------
        # 6. DETECT SECTIONS + CHUNK
        # ------------------------------------------------------------------
        sections = detect_judgment_sections(full_text)
        chunks = chunk_judgment(full_text, sections, case_id=case_id)
        logger.info("case_id=%s: %d sections, %d chunks", case_id, len(sections), len(chunks))

        # ------------------------------------------------------------------
        # 6b. PERSIST SECTIONS + CITATION EQUIVALENTS
        # ------------------------------------------------------------------
        await _persist_sections(str(case_id), sections, db)
        citation_equivalents = _extract_citation_equivalents(full_text, str(case_id))
        if citation_equivalents:
            await _persist_citation_equivalents(citation_equivalents, db)

        # ------------------------------------------------------------------
        # 7. GENERATE EMBEDDINGS
        # ------------------------------------------------------------------
        embeddings = await _embed_chunks(chunks, embedder, rate_limiter=rate_limiter)
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"Embedding count mismatch: {len(embeddings)} embeddings "
                f"for {len(chunks)} chunks (case_id={case_id})"
            )

        # ------------------------------------------------------------------
        # 8. UPSERT TO VECTOR STORE
        # ------------------------------------------------------------------
        await _upsert_vectors(case_id, chunks, embeddings, metadata, vector_store)

        # Update chunk_count in PostgreSQL
        await db.execute(
            text("UPDATE cases SET chunk_count = :count WHERE id = :id"),
            {"count": len(chunks), "id": case_id},
        )
        await db.commit()

        # ------------------------------------------------------------------
        # 9. BUILD CITATION GRAPH
        # ------------------------------------------------------------------
        await _build_citation_graph(case_id, metadata, full_text, graph_store)

    except Exception as exc:
        logger.exception("Ingestion failed after case insert for case_id=%s", case_id)
        await _record_ingestion_failure(db, case_id, pdf_path, str(exc)[:2000])
        raise

    logger.info("Ingestion complete: case_id=%s, chunks=%d", case_id, len(chunks))
    return case_id


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _safe_filename(parquet_meta: dict) -> str:
    """Generate a safe filename from parquet metadata."""
    title = parquet_meta.get("title", "unknown")
    # Keep only alphanumeric and basic punctuation
    safe = "".join(c if c.isalnum() or c in "._- " else "" for c in title)
    return f"{safe[:80].strip()}.pdf" if safe.strip() else "judgment.pdf"


async def _insert_case(
    db: AsyncSession,
    case_id: str,
    metadata: CaseMetadata,
    full_text: str,
    storage_path: str,
    parquet_meta: dict,
) -> str:
    """Insert or update a case record into PostgreSQL. Returns the case_id used."""
    # Parse decision_date to a proper date object
    decision_date: date | None = None
    if metadata.decision_date:
        try:
            decision_date = datetime.fromisoformat(metadata.decision_date).date()
        except ValueError:
            pass

    params = {
        "id": case_id,
        "title": metadata.title or parquet_meta.get("title", "Untitled"),
        "citation": metadata.citation,
        "case_id": parquet_meta.get("case_id"),
        "cnr": parquet_meta.get("cnr"),
        "court": metadata.court or "Supreme Court of India",
        "year": metadata.year,
        "case_type": metadata.case_type,
        "jurisdiction": metadata.jurisdiction,
        "bench_type": metadata.bench_type,
        "judge": metadata.judge,
        "author_judge": metadata.author_judge,
        "petitioner": metadata.petitioner,
        "respondent": metadata.respondent,
        "decision_date": decision_date,
        "disposal_nature": metadata.disposal_nature,
        "description": parquet_meta.get("description"),
        "keywords": metadata.keywords,
        "acts_cited": metadata.acts_cited,
        "cases_cited": metadata.cases_cited,
        "ratio_decidendi": metadata.ratio_decidendi,
        "full_text": full_text,
        "pdf_storage_path": storage_path,
        "s3_source_path": parquet_meta.get("path"),
        "source": "aws_open_data",
        "language": "english",
        "available_languages": (
            parquet_meta.get("available_languages", "").split(",")
            if parquet_meta.get("available_languages")
            else None
        ),
    }

    # Use INSERT ... ON CONFLICT to handle duplicate citation race condition
    result = await db.execute(
        text(
            """
            INSERT INTO cases (
                id, title, citation, case_id, cnr, court, year, case_type,
                jurisdiction, bench_type, judge, author_judge, petitioner,
                respondent, decision_date, disposal_nature, description,
                keywords, acts_cited, cases_cited, ratio_decidendi,
                full_text, searchable_text, pdf_storage_path, s3_source_path,
                source, language, available_languages, chunk_count
            ) VALUES (
                :id, :title, :citation, :case_id, :cnr, :court, :year, :case_type,
                :jurisdiction, :bench_type, :judge, :author_judge, :petitioner,
                :respondent, :decision_date, :disposal_nature, :description,
                :keywords, :acts_cited, :cases_cited, :ratio_decidendi,
                :full_text,
                to_tsvector('english', COALESCE(:title, '') || ' ' || COALESCE(:citation, '') || ' ' || COALESCE(LEFT(:full_text, 50000), '')),
                :pdf_storage_path, :s3_source_path, :source,
                :language, :available_languages, 0
            )
            ON CONFLICT (citation) WHERE citation IS NOT NULL DO UPDATE SET
                full_text = EXCLUDED.full_text,
                pdf_storage_path = EXCLUDED.pdf_storage_path,
                ratio_decidendi = COALESCE(EXCLUDED.ratio_decidendi, cases.ratio_decidendi),
                acts_cited = COALESCE(EXCLUDED.acts_cited, cases.acts_cited),
                cases_cited = COALESCE(EXCLUDED.cases_cited, cases.cases_cited),
                keywords = COALESCE(EXCLUDED.keywords, cases.keywords),
                bench_type = COALESCE(EXCLUDED.bench_type, cases.bench_type),
                jurisdiction = COALESCE(EXCLUDED.jurisdiction, cases.jurisdiction),
                searchable_text = EXCLUDED.searchable_text
            RETURNING id
            """
        ),
        params,
    )
    row = result.fetchone()
    await db.commit()

    if row is None and metadata.citation:
        # Citation already existed -- fetch the existing case ID
        existing = await db.execute(
            text("SELECT id FROM cases WHERE citation = :citation"),
            {"citation": metadata.citation},
        )
        existing_row = existing.fetchone()
        if existing_row:
            logger.info(
                "Case with citation %s already exists (id=%s), skipping insert",
                metadata.citation, existing_row[0],
            )
            return str(existing_row[0])

    return case_id


async def _record_ingestion_failure(
    db: AsyncSession,
    case_id: str,
    pdf_path: str,
    error_message: str,
) -> None:
    """Record an ingestion failure in the audit_logs table for tracking."""
    await db.execute(
        text(
            "INSERT INTO audit_logs (action, resource_type, resource_id, metadata, created_at) "
            "VALUES (:action, :resource_type, :resource_id, :metadata, NOW())"
        ),
        {
            "action": "ingestion.failed",
            "resource_type": "case",
            "resource_id": case_id,
            "metadata": json.dumps({"pdf_path": pdf_path, "error": error_message}),
        },
    )
    await db.commit()


async def _embed_chunks(
    chunks: list[Chunk],
    embedder: EmbeddingProvider,
    max_retries: int = 3,
    *,
    rate_limiter: AsyncRateLimiter | None = None,
) -> list[list[float]]:
    """Generate embeddings for chunks in batches with retry logic."""
    all_embeddings: list[list[float]] = []
    texts = [c.text for c in chunks]

    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[i : i + _EMBED_BATCH_SIZE]
        for attempt in range(max_retries):
            try:
                if rate_limiter:
                    await rate_limiter.acquire()
                batch_embeddings = await embedder.embed_batch(batch)
                all_embeddings.extend(batch_embeddings)
                break
            except Exception as exc:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** attempt
                logger.warning(
                    "Embedding batch %d failed (attempt %d/%d), retrying in %ds: %s",
                    i // _EMBED_BATCH_SIZE, attempt + 1, max_retries, wait, exc,
                )
                await asyncio.sleep(wait)

    return all_embeddings


async def _upsert_vectors(
    case_id: str,
    chunks: list[Chunk],
    embeddings: list[list[float]],
    metadata: CaseMetadata,
    vector_store: VectorStore,
) -> None:
    """Upsert chunk vectors to the vector store with metadata."""
    vectors: list[dict] = []
    for chunk, embedding in zip(chunks, embeddings):
        vector_id = f"{case_id}_{chunk.chunk_index}"
        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": {
                "case_id": case_id,
                "chunk_index": chunk.chunk_index,
                "section_type": chunk.section_type,
                "court": metadata.court or "",
                "year": metadata.year or 0,
                "case_type": metadata.case_type or "",
                "jurisdiction": metadata.jurisdiction or "",
                "text": chunk.text[:1000],  # Pinecone metadata size limit
            },
        })

    # Upsert in batches of 100 (Pinecone recommended batch size)
    for i in range(0, len(vectors), 100):
        await vector_store.upsert(vectors[i : i + 100])


async def _build_citation_graph(
    case_id: str,
    metadata: CaseMetadata,
    full_text: str,
    graph_store: GraphStore,
) -> None:
    """Create the case node and citation edges in Neo4j."""
    # Create the case node
    try:
        await graph_store.create_node(
            "Case",
            {
                "id": case_id,
                "title": metadata.title or "",
                "citation": metadata.citation or "",
                "court": metadata.court or "",
                "year": metadata.year or 0,
            },
        )
    except (OSError, ConnectionError, RuntimeError) as exc:
        logger.error("Failed to create case node %s: %s", case_id, exc)
        return

    # Extract citations from the text
    citations = extract_citations(full_text)

    # Create CITES edges for each cited case
    for citation in citations:
        cited_ref = citation.raw_text
        try:
            # Create a placeholder node for the cited case (if not already present)
            await graph_store.query(
                "MERGE (c:Case {citation: $citation}) "
                "ON CREATE SET c.id = $placeholder_id, c.title = $citation",
                params={
                    "citation": cited_ref,
                    "placeholder_id": f"ref_{uuid.uuid4().hex[:12]}",
                },
            )
            # Create the CITES edge with treatment metadata
            await graph_store.query(
                "MATCH (a:Case {id: $from_id}), (b:Case {citation: $to_citation}) "
                "MERGE (a)-[:CITES {reporter: $reporter, treatment: $treatment}]->(b)",
                params={
                    "from_id": case_id,
                    "to_citation": cited_ref,
                    "reporter": citation.reporter,
                    "treatment": citation.treatment if hasattr(citation, "treatment") else "",
                },
            )
        except (OSError, ConnectionError, RuntimeError):
            logger.warning("Failed to create citation edge: %s -> %s", case_id, cited_ref)


def _extract_citation_equivalents(full_text: str, case_id: str) -> list[dict]:
    """Extract all citation formats from judgment text for the equivalents table."""
    if not full_text:
        return []
    citations = extract_citations(full_text)
    results = []
    for c in citations:
        results.append({
            "case_id": case_id,
            "reporter": c.reporter,
            "citation_text": c.raw_text,
            "year": c.year,
        })
    return results


async def _persist_sections(
    case_id: str,
    sections: list,
    db: AsyncSession,
) -> None:
    """Persist detected judgment sections to the case_sections table."""
    if not sections:
        return
    for idx, section in enumerate(sections):
        await db.execute(
            text(
                "INSERT INTO case_sections (id, case_id, section_type, content, section_index) "
                "VALUES (:id, :case_id, :section_type, :content, :section_index) "
                "ON CONFLICT DO NOTHING"
            ),
            {
                "id": str(uuid.uuid4()),
                "case_id": str(case_id),
                "section_type": section.type,
                "content": section.text,
                "section_index": idx,
            },
        )
    await db.commit()


async def _persist_citation_equivalents(
    equivalents: list[dict],
    db: AsyncSession,
) -> None:
    """Persist citation equivalents to the database."""
    if not equivalents:
        return
    for eq in equivalents:
        await db.execute(
            text(
                "INSERT INTO case_citation_equivalents (id, case_id, reporter, citation_text, year) "
                "VALUES (:id, :case_id, :reporter, :citation_text, :year) "
                "ON CONFLICT DO NOTHING"
            ),
            {
                "id": str(uuid.uuid4()),
                "case_id": str(eq["case_id"]),
                "reporter": eq["reporter"],
                "citation_text": eq["citation_text"],
                "year": eq["year"],
            },
        )
    await db.commit()


# ---------------------------------------------------------------------------
# Batch / bulk ingestion helpers
# ---------------------------------------------------------------------------

# Maximum rows per INSERT statement for batch operations.
_BATCH_CHUNK_SIZE: int = 250


@dataclass
class BatchStats:
    """Statistics returned by ``ingest_batch``."""

    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] | None = None


async def bulk_upsert_cases(
    cases_data: list[dict[str, Any]],
    db: AsyncSession,
    *,
    batch_size: int = _BATCH_CHUNK_SIZE,
) -> list[str]:
    """Bulk upsert cases into PostgreSQL using multi-value INSERT.

    Each dict in *cases_data* should have the same keys as the columns in the
    ``cases`` table (see ``_insert_case`` for reference).  At minimum: ``id``,
    ``title``, ``court``.

    Uses ``INSERT ... ON CONFLICT (citation) DO UPDATE`` so rows with an
    existing citation are updated rather than duplicated.

    Returns:
        List of case IDs (UUIDs as strings) that were inserted or updated.
    """
    if not cases_data:
        return []

    all_ids: list[str] = []

    stmt = text(
        """
        INSERT INTO cases (
            id, title, citation, case_id, cnr, court, year, case_type,
            jurisdiction, bench_type, judge, author_judge, petitioner,
            respondent, decision_date, disposal_nature, description,
            keywords, acts_cited, cases_cited, ratio_decidendi,
            full_text, searchable_text, pdf_storage_path, s3_source_path,
            source, language, available_languages, chunk_count
        ) VALUES (
            :id, :title, :citation, :case_id, :cnr, :court, :year, :case_type,
            :jurisdiction, :bench_type, :judge, :author_judge, :petitioner,
            :respondent, :decision_date, :disposal_nature, :description,
            :keywords, :acts_cited, :cases_cited, :ratio_decidendi,
            :full_text,
            to_tsvector('english', COALESCE(:title, '') || ' '
                || COALESCE(:citation, '') || ' '
                || COALESCE(LEFT(:full_text, 50000), '')),
            :pdf_storage_path, :s3_source_path, :source,
            :language, :available_languages, :chunk_count
        )
        ON CONFLICT (citation) WHERE citation IS NOT NULL DO UPDATE SET
            full_text = EXCLUDED.full_text,
            pdf_storage_path = EXCLUDED.pdf_storage_path,
            ratio_decidendi = COALESCE(EXCLUDED.ratio_decidendi, cases.ratio_decidendi),
            acts_cited = COALESCE(EXCLUDED.acts_cited, cases.acts_cited),
            cases_cited = COALESCE(EXCLUDED.cases_cited, cases.cases_cited),
            keywords = COALESCE(EXCLUDED.keywords, cases.keywords),
            bench_type = COALESCE(EXCLUDED.bench_type, cases.bench_type),
            jurisdiction = COALESCE(EXCLUDED.jurisdiction, cases.jurisdiction),
            searchable_text = EXCLUDED.searchable_text
        RETURNING id
        """
    )

    for start in range(0, len(cases_data), batch_size):
        batch = cases_data[start : start + batch_size]

        for row in batch:
            row_id = str(row.get("id") or uuid.uuid4())
            params = {
                "id": row_id,
                "title": row.get("title", "Untitled"),
                "citation": row.get("citation"),
                "case_id": row.get("case_id"),
                "cnr": row.get("cnr"),
                "court": row.get("court", "Supreme Court of India"),
                "year": row.get("year"),
                "case_type": row.get("case_type"),
                "jurisdiction": row.get("jurisdiction"),
                "bench_type": row.get("bench_type"),
                "judge": row.get("judge"),
                "author_judge": row.get("author_judge"),
                "petitioner": row.get("petitioner"),
                "respondent": row.get("respondent"),
                "decision_date": row.get("decision_date"),
                "disposal_nature": row.get("disposal_nature"),
                "description": row.get("description"),
                "keywords": row.get("keywords"),
                "acts_cited": row.get("acts_cited"),
                "cases_cited": row.get("cases_cited"),
                "ratio_decidendi": row.get("ratio_decidendi"),
                "full_text": row.get("full_text"),
                "pdf_storage_path": row.get("pdf_storage_path"),
                "s3_source_path": row.get("s3_source_path"),
                "source": row.get("source", "aws_open_data"),
                "language": row.get("language", "english"),
                "available_languages": row.get("available_languages"),
                "chunk_count": row.get("chunk_count", 0),
            }
            result = await db.execute(stmt, params)
            returned = result.fetchone()
            all_ids.append(str(returned[0]) if returned else row_id)

    await db.flush()
    logger.info("bulk_upsert_cases: processed %d rows", len(all_ids))
    return all_ids


async def bulk_insert_sections(
    sections_data: list[dict[str, Any]],
    db: AsyncSession,
    *,
    batch_size: int = _BATCH_CHUNK_SIZE,
) -> int:
    """Bulk INSERT into ``case_sections`` using executemany pattern.

    Each dict must contain: ``case_id``, ``section_type``, ``content``,
    ``section_index``.  An ``id`` (UUID) will be generated if absent.

    Returns:
        Number of rows inserted.
    """
    if not sections_data:
        return 0

    inserted = 0
    stmt = text(
        "INSERT INTO case_sections (id, case_id, section_type, content, section_index) "
        "VALUES (:id, :case_id, :section_type, :content, :section_index) "
        "ON CONFLICT DO NOTHING"
    )

    for start in range(0, len(sections_data), batch_size):
        batch = sections_data[start : start + batch_size]
        for row in batch:
            params = {
                "id": str(row.get("id") or uuid.uuid4()),
                "case_id": str(row["case_id"]),
                "section_type": row["section_type"],
                "content": row["content"],
                "section_index": row.get("section_index", 0),
            }
            await db.execute(stmt, params)
            inserted += 1

    await db.flush()
    logger.info("bulk_insert_sections: inserted %d rows", inserted)
    return inserted


async def bulk_insert_citations(
    citations_data: list[dict[str, Any]],
    db: AsyncSession,
    *,
    batch_size: int = _BATCH_CHUNK_SIZE,
) -> int:
    """Bulk INSERT into ``case_citation_equivalents`` with ON CONFLICT DO NOTHING.

    Each dict must contain: ``case_id``, ``reporter``, ``citation_text``.
    Optional: ``year``.

    Returns:
        Number of rows processed (some may be skipped due to conflicts).
    """
    if not citations_data:
        return 0

    processed = 0
    stmt = text(
        "INSERT INTO case_citation_equivalents (id, case_id, reporter, citation_text, year) "
        "VALUES (:id, :case_id, :reporter, :citation_text, :year) "
        "ON CONFLICT DO NOTHING"
    )

    for start in range(0, len(citations_data), batch_size):
        batch = citations_data[start : start + batch_size]
        for row in batch:
            params = {
                "id": str(row.get("id") or uuid.uuid4()),
                "case_id": str(row["case_id"]),
                "reporter": row["reporter"],
                "citation_text": row["citation_text"],
                "year": row.get("year"),
            }
            await db.execute(stmt, params)
            processed += 1

    await db.flush()
    logger.info("bulk_insert_citations: processed %d rows", processed)
    return processed


async def ingest_batch(
    judgments: list[dict[str, Any]],
    db: AsyncSession,
) -> BatchStats:
    """Orchestrate bulk ingestion of pre-processed judgments.

    Each dict in *judgments* should have:
    - All ``cases`` table columns (same keys as ``bulk_upsert_cases``).
    - ``"sections"`` (optional): list of section dicts for the case.
    - ``"citation_equivalents"`` (optional): list of citation-equivalent dicts.

    Everything runs inside the caller's transaction (no internal commit).
    The caller should ``await db.commit()`` after a successful return.

    Returns:
        A ``BatchStats`` dataclass with counts.
    """
    stats = BatchStats(errors=[])
    if not judgments:
        return stats

    # ---- 1. Prepare cases data (strip nested keys) ----
    cases_data: list[dict[str, Any]] = []
    all_sections: list[dict[str, Any]] = []
    all_citations: list[dict[str, Any]] = []

    for jdg in judgments:
        # Pull out nested collections before passing to bulk upsert
        sections = jdg.pop("sections", None) or []
        cit_equivalents = jdg.pop("citation_equivalents", None) or []

        case_id = str(jdg.get("id") or uuid.uuid4())
        jdg["id"] = case_id
        cases_data.append(jdg)

        # Tag child rows with the parent case_id
        for sec in sections:
            sec.setdefault("case_id", case_id)
            all_sections.append(sec)

        for cit in cit_equivalents:
            cit.setdefault("case_id", case_id)
            all_citations.append(cit)

    # ---- 2. Bulk upsert cases ----
    try:
        inserted_ids = await bulk_upsert_cases(cases_data, db)
        stats.inserted = len(inserted_ids)
    except Exception as exc:
        logger.exception("bulk_upsert_cases failed")
        stats.failed = len(cases_data)
        if stats.errors is not None:
            stats.errors.append(f"bulk_upsert_cases: {exc}")
        return stats

    # ---- 3. Bulk insert sections ----
    if all_sections:
        try:
            await bulk_insert_sections(all_sections, db)
        except Exception as exc:
            logger.exception("bulk_insert_sections failed")
            if stats.errors is not None:
                stats.errors.append(f"bulk_insert_sections: {exc}")

    # ---- 4. Bulk insert citation equivalents ----
    if all_citations:
        try:
            await bulk_insert_citations(all_citations, db)
        except Exception as exc:
            logger.exception("bulk_insert_citations failed")
            if stats.errors is not None:
                stats.errors.append(f"bulk_insert_citations: {exc}")

    logger.info(
        "ingest_batch complete: inserted=%d, skipped=%d, failed=%d",
        stats.inserted, stats.skipped, stats.failed,
    )
    return stats
