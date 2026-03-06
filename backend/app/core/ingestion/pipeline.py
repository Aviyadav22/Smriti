"""Ingestion pipeline orchestrator for Indian court judgments.

Coordinates the full pipeline: PDF → text → metadata → chunks → embeddings → store.
Follows the architecture defined in DATA_SOURCES.md §3.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion.chunker import Chunk, chunk_judgment, detect_judgment_sections
from app.core.ingestion.metadata import (
    CaseMetadata,
    extract_metadata_llm,
    merge_metadata,
    validate_with_regex,
)
from app.core.ingestion.pdf import extract_pdf_text, extract_with_ocr
from app.core.interfaces.embedder import EmbeddingProvider
from app.core.interfaces.graph_store import GraphStore
from app.core.interfaces.llm import LLMProvider
from app.core.interfaces.storage import FileStorage
from app.core.interfaces.vector_store import VectorStore
from app.core.legal.courts import normalize_court_name
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

    Returns:
        The case UUID as a string.
    """
    case_id = str(uuid.uuid4())
    logger.info("Starting ingestion for case_id=%s, pdf=%s", case_id, pdf_path)

    # ------------------------------------------------------------------
    # 1. EXTRACT TEXT
    # ------------------------------------------------------------------
    full_text = await extract_pdf_text(pdf_path)
    if not full_text or len(full_text) < 100:
        logger.warning("pdfplumber extraction insufficient, trying OCR: %s", pdf_path)
        full_text = await extract_with_ocr(pdf_path)

    if not full_text or len(full_text) < 50:
        logger.error("No text extracted from PDF: %s", pdf_path)
        await _record_ingestion_failure(db, case_id, pdf_path, "No text extracted")
        return case_id

    # ------------------------------------------------------------------
    # 2. MERGE METADATA (Parquet + LLM)
    # ------------------------------------------------------------------
    llm_meta = await extract_metadata_llm(full_text, llm)
    metadata = merge_metadata(parquet_metadata, llm_meta)

    # ------------------------------------------------------------------
    # 3. VALIDATE METADATA
    # ------------------------------------------------------------------
    metadata = validate_with_regex(metadata)

    # Normalize court name
    if metadata.court:
        metadata.court = normalize_court_name(metadata.court)

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

    # ------------------------------------------------------------------
    # 6. DETECT SECTIONS + CHUNK
    # ------------------------------------------------------------------
    sections = detect_judgment_sections(full_text)
    chunks = chunk_judgment(full_text, sections, case_id=case_id)
    logger.info("case_id=%s: %d sections, %d chunks", case_id, len(sections), len(chunks))

    # ------------------------------------------------------------------
    # 7. GENERATE EMBEDDINGS
    # ------------------------------------------------------------------
    embeddings = await _embed_chunks(chunks, embedder)

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

    # Check if a case with this citation already exists
    if metadata.citation:
        existing = await db.execute(
            text("SELECT id FROM cases WHERE citation = :citation"),
            {"citation": metadata.citation},
        )
        row = existing.fetchone()
        if row:
            logger.info("Case with citation %s already exists (id=%s), skipping insert", metadata.citation, row[0])
            await db.commit()
            return str(row[0])

    await db.execute(
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
            """
        ),
        params,
    )
    await db.commit()
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
) -> list[list[float]]:
    """Generate embeddings for chunks in batches."""
    all_embeddings: list[list[float]] = []
    texts = [c.text for c in chunks]

    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[i : i + _EMBED_BATCH_SIZE]
        batch_embeddings = await embedder.embed_batch(batch)
        all_embeddings.extend(batch_embeddings)

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
            # Create the CITES edge
            await graph_store.query(
                "MATCH (a:Case {id: $from_id}), (b:Case {citation: $to_citation}) "
                "MERGE (a)-[:CITES {reporter: $reporter}]->(b)",
                params={
                    "from_id": case_id,
                    "to_citation": cited_ref,
                    "reporter": citation.reporter,
                },
            )
        except (OSError, ConnectionError, RuntimeError):
            logger.warning("Failed to create citation edge: %s -> %s", case_id, cited_ref)
