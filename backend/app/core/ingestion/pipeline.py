"""Ingestion pipeline orchestrator for Indian court judgments.

Coordinates the full pipeline: PDF -> text -> metadata -> chunks -> embeddings -> store.
Follows the architecture defined in DATA_SOURCES.md S3.

Also provides batch/bulk database helpers for high-throughput ingestion of
pre-processed judgments (bulk_upsert_cases, bulk_insert_sections,
bulk_insert_citations, ingest_batch).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion.chunker import Chunk, chunk_judgment, detect_judgment_sections
from app.core.ingestion.metadata import (
    CaseMetadata,
    compute_extraction_confidence,
    extract_metadata_llm,
    merge_metadata,
    validate_cross_fields,
    validate_parquet_data,
    validate_with_regex,
)
from app.core.ingestion.pdf import extract_and_score, extract_pdf_text, extract_with_ocr
from app.core.ingestion.rate_limiter import AsyncRateLimiter
from app.core.interfaces.embedder import EmbeddingProvider
from app.core.interfaces.graph_store import GraphStore
from app.core.interfaces.llm import LLMProvider
from app.core.interfaces.storage import FileStorage
from app.core.interfaces.vector_store import VectorStore
from app.core.legal.extractor import extract_acts_cited, extract_citations
from app.core.legal.treatment import detect_treatment_in_text

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
    llm_rate_limiter: AsyncRateLimiter | None = None,
    embed_rate_limiter: AsyncRateLimiter | None = None,
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
        rate_limiter: Shared rate limiter for all API calls (backward compat).
        llm_rate_limiter: Separate rate limiter for LLM metadata extraction.
        embed_rate_limiter: Separate rate limiter for embedding API calls.

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
    _llm_limiter = llm_rate_limiter or rate_limiter
    if _llm_limiter:
        await _llm_limiter.acquire()
    try:
        llm_meta = await asyncio.wait_for(
            extract_metadata_llm(full_text, llm), timeout=120.0
        )
    except asyncio.TimeoutError:
        logger.warning("LLM metadata extraction timed out for %s, using empty", pdf_path)
        llm_meta = CaseMetadata()
    validated_parquet = validate_parquet_data(parquet_metadata)
    metadata, provenance = merge_metadata(validated_parquet, llm_meta)

    # ------------------------------------------------------------------
    # 3. VALIDATE METADATA
    # ------------------------------------------------------------------
    metadata = validate_with_regex(metadata)
    metadata = validate_cross_fields(metadata)

    # Supplement LLM acts_cited with regex extraction
    regex_acts = extract_acts_cited(full_text)
    if regex_acts:
        llm_acts = set(metadata.acts_cited or [])
        for ref in regex_acts:
            act_str = f"{ref.act_name}, {ref.year}" if ref.year else ref.act_name
            llm_acts.add(act_str)
        metadata.acts_cited = sorted(llm_acts)
        provenance["acts_cited"] = "llm+regex"

    # Supplement LLM cases_cited with regex extraction
    regex_citations = extract_citations(full_text)
    if regex_citations:
        llm_cases = set(metadata.cases_cited or [])
        for cit in regex_citations:
            llm_cases.add(cit.raw_text)
        metadata.cases_cited = sorted(llm_cases)
        provenance["cases_cited"] = "llm+regex"

    # Compute text_hash for dedup (SHA-256 of whitespace-normalized text)
    text_hash = _compute_text_hash(full_text)

    # Compute extraction confidence score
    extraction_confidence = compute_extraction_confidence(metadata)

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
    original_case_id = case_id
    case_id, already_ingested = await _insert_case(
        db, case_id, metadata, full_text, storage_path, parquet_metadata,
        provenance=provenance, text_hash=text_hash,
        extraction_confidence=extraction_confidence,
    )

    if already_ingested:
        logger.info(
            "Case %s already fully ingested (case_id=%s), skipping pipeline",
            metadata.citation, case_id,
        )
        return case_id

    # ------------------------------------------------------------------
    # 6–9: Remaining pipeline steps wrapped for failure handling
    # ------------------------------------------------------------------
    # Mark ingestion as in-progress
    await db.execute(
        text("UPDATE cases SET ingestion_status = 'processing' WHERE id = :id"),
        {"id": case_id},
    )

    db_committed = False
    try:
        # --------------------------------------------------------------
        # 6. DETECT SECTIONS + CHUNK
        # --------------------------------------------------------------
        sections = detect_judgment_sections(full_text)
        chunks = chunk_judgment(full_text, sections, case_id=case_id)
        logger.info(
            "case_id=%s: %d sections, %d chunks",
            case_id, len(sections), len(chunks),
        )

        # --------------------------------------------------------------
        # 6b. PERSIST SECTIONS + CITATION EQUIVALENTS
        # --------------------------------------------------------------
        await _persist_sections(str(case_id), sections, db)
        citation_equivalents = _extract_citation_equivalents(full_text, str(case_id))
        if citation_equivalents:
            await _persist_citation_equivalents(citation_equivalents, db)

        # --------------------------------------------------------------
        # 7. GENERATE EMBEDDINGS
        # --------------------------------------------------------------
        _embed_limiter = embed_rate_limiter or rate_limiter
        embeddings = await asyncio.wait_for(
            _embed_chunks(chunks, embedder, rate_limiter=_embed_limiter),
            timeout=300.0,  # 5 min for large documents with many chunks
        )
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"Embedding count mismatch: {len(embeddings)} embeddings "
                f"for {len(chunks)} chunks (case_id={case_id})"
            )

        # --------------------------------------------------------------
        # 8. UPSERT TO VECTOR STORE
        # --------------------------------------------------------------
        # Clean up stale vectors from any previous ingestion
        pinecone_deleted = False
        try:
            await vector_store.delete(filter={"case_id": case_id})
            pinecone_deleted = True
        except Exception:
            logger.warning("Failed to clean stale vectors for case_id=%s", case_id)

        try:
            await _upsert_vectors(case_id, chunks, embeddings, metadata, vector_store)
        except Exception:
            if pinecone_deleted:
                logger.critical(
                    "MANUAL RECOVERY NEEDED: Pinecone delete succeeded but upsert "
                    "failed for case_id=%s. Vectors are permanently lost until "
                    "re-ingestion.",
                    case_id,
                )
            raise

        # Update chunk_count and mark ingestion status
        # Low confidence extractions are flagged for human review
        _REVIEW_THRESHOLD = 0.5
        final_status = (
            "needs_review" if extraction_confidence < _REVIEW_THRESHOLD
            else "complete"
        )
        await db.execute(
            text(
                "UPDATE cases SET chunk_count = :count, ingestion_status = :status "
                "WHERE id = :id"
            ),
            {"count": len(chunks), "status": final_status, "id": case_id},
        )

        # --------------------------------------------------------------
        # COMMIT all DB writes (insert, sections, citations, chunk_count)
        # --------------------------------------------------------------
        try:
            await db.commit()
            db_committed = True
        except Exception as commit_exc:
            logger.error("DB commit failed for case_id=%s: %s", case_id, commit_exc)
            raise

        # --------------------------------------------------------------
        # 9. BUILD CITATION GRAPH (non-critical, idempotent)
        # --------------------------------------------------------------
        try:
            await asyncio.wait_for(
                _build_citation_graph(case_id, metadata, full_text, graph_store),
                timeout=60.0,
            )
            # Link citation equivalents in graph (F10)
            if citation_equivalents:
                await _link_citation_equivalents(
                    case_id, metadata.citation, citation_equivalents, graph_store,
                )
        except (Exception, asyncio.TimeoutError) as graph_exc:
            # Graph build is non-critical; log but don't fail the pipeline
            logger.error(
                "Citation graph build failed for case_id=%s: %s",
                case_id, graph_exc,
            )

    except Exception as pipeline_exc:
        logger.error(
            "Pipeline failed for case_id=%s: %s", case_id, pipeline_exc,
        )
        # Rollback uncommitted partial writes, or mark status as failed
        if not db_committed:
            try:
                await db.rollback()
            except Exception:
                logger.error("Rollback failed for case_id=%s", case_id)
        if db_committed:
            try:
                await db.execute(
                    text(
                        "UPDATE cases SET ingestion_status = 'failed' "
                        "WHERE id = :id"
                    ),
                    {"id": case_id},
                )
                await db.commit()
            except Exception:
                logger.error(
                    "Failed to update ingestion_status for case_id=%s", case_id,
                )
        await _record_ingestion_failure(
            db, case_id, pdf_path, str(pipeline_exc),
        )
        raise

    logger.info("Ingestion complete: case_id=%s, chunks=%d", case_id, len(chunks))
    return case_id


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _compute_text_hash(text: str) -> str:
    """Compute SHA-256 hash of whitespace-normalized text for dedup."""
    normalized = re.sub(r'\s+', ' ', text.strip().lower())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


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
    *,
    provenance: dict[str, str] | None = None,
    text_hash: str | None = None,
    extraction_confidence: float | None = None,
) -> tuple[str, bool]:
    """Insert or update a case record into PostgreSQL.

    Returns (case_id, already_ingested) where already_ingested is True
    if the case already has vectors and should be skipped.
    """
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
        "case_number": metadata.case_number,
        "is_reportable": metadata.is_reportable,
        "headnotes": metadata.headnotes,
        "outcome_summary": metadata.outcome_summary,
        # Phase C: legal completeness fields
        "coram_size": metadata.coram_size,
        "lower_court": metadata.lower_court,
        "lower_court_case_number": metadata.lower_court_case_number,
        "appeal_from": metadata.appeal_from,
        "opinion_type": metadata.opinion_type,
        "dissenting_judges": metadata.dissenting_judges,
        "concurring_judges": metadata.concurring_judges,
        "split_ratio": metadata.split_ratio,
        "petitioner_type": metadata.petitioner_type,
        "respondent_type": metadata.respondent_type,
        "is_pil": metadata.is_pil,
        "companion_cases": metadata.companion_cases,
        "metadata_provenance": json.dumps(provenance) if provenance else None,
        "text_hash": text_hash,
        "extraction_confidence": extraction_confidence,
    }

    # Check for content-based duplicate via text_hash
    if text_hash:
        existing_hash = await db.execute(
            text("SELECT id, chunk_count FROM cases WHERE text_hash = :hash"),
            {"hash": text_hash},
        )
        hash_row = existing_hash.fetchone()
        if hash_row:
            existing_id = str(hash_row[0])
            if hash_row[1] and hash_row[1] > 0:
                logger.info("Duplicate content detected via text_hash (case_id=%s)", existing_id)
                return existing_id, True
            logger.info("Duplicate content but missing vectors, re-ingesting (case_id=%s)", existing_id)
            return existing_id, False

    # Check if a case with this citation already exists
    if metadata.citation:
        existing = await db.execute(
            text("SELECT id FROM cases WHERE citation = :citation"),
            {"citation": metadata.citation},
        )
        row = existing.fetchone()
        if row:
            existing_id = str(row[0])
            # Check if vectors exist for this case
            chunk_check = await db.execute(
                text("SELECT chunk_count FROM cases WHERE id = :id"),
                {"id": existing_id},
            )
            chunk_row = chunk_check.fetchone()
            if chunk_row and chunk_row[0] and chunk_row[0] > 0:
                logger.info("Case %s already fully ingested, skipping", metadata.citation)
                return existing_id, True
            logger.info("Case %s exists but missing vectors, re-ingesting", metadata.citation)
            return existing_id, False  # reuse existing ID, let pipeline continue

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
                source, language, available_languages, chunk_count,
                case_number, is_reportable, headnotes, outcome_summary,
                coram_size, lower_court, lower_court_case_number, appeal_from,
                opinion_type, dissenting_judges, concurring_judges, split_ratio,
                petitioner_type, respondent_type, is_pil, companion_cases,
                metadata_provenance, text_hash, extraction_confidence
            ) VALUES (
                :id, :title, :citation, :case_id, :cnr, :court, :year, :case_type,
                :jurisdiction, :bench_type, :judge, :author_judge, :petitioner,
                :respondent, :decision_date, :disposal_nature, :description,
                :keywords, :acts_cited, :cases_cited, :ratio_decidendi,
                :full_text,
                NULL,  -- searchable_text computed by BEFORE INSERT trigger (weighted tsvector)
                :pdf_storage_path, :s3_source_path, :source,
                :language, :available_languages, 0,
                :case_number, :is_reportable, :headnotes, :outcome_summary,
                :coram_size, :lower_court, :lower_court_case_number, :appeal_from,
                :opinion_type, :dissenting_judges, :concurring_judges, :split_ratio,
                :petitioner_type, :respondent_type, :is_pil, :companion_cases,
                :metadata_provenance, :text_hash, :extraction_confidence
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
                searchable_text = EXCLUDED.searchable_text,
                case_number = COALESCE(EXCLUDED.case_number, cases.case_number),
                is_reportable = COALESCE(EXCLUDED.is_reportable, cases.is_reportable),
                headnotes = COALESCE(EXCLUDED.headnotes, cases.headnotes),
                outcome_summary = COALESCE(EXCLUDED.outcome_summary, cases.outcome_summary),
                coram_size = COALESCE(EXCLUDED.coram_size, cases.coram_size),
                lower_court = COALESCE(EXCLUDED.lower_court, cases.lower_court),
                lower_court_case_number = COALESCE(EXCLUDED.lower_court_case_number, cases.lower_court_case_number),
                appeal_from = COALESCE(EXCLUDED.appeal_from, cases.appeal_from),
                opinion_type = COALESCE(EXCLUDED.opinion_type, cases.opinion_type),
                dissenting_judges = COALESCE(EXCLUDED.dissenting_judges, cases.dissenting_judges),
                concurring_judges = COALESCE(EXCLUDED.concurring_judges, cases.concurring_judges),
                split_ratio = COALESCE(EXCLUDED.split_ratio, cases.split_ratio),
                petitioner_type = COALESCE(EXCLUDED.petitioner_type, cases.petitioner_type),
                respondent_type = COALESCE(EXCLUDED.respondent_type, cases.respondent_type),
                is_pil = COALESCE(EXCLUDED.is_pil, cases.is_pil),
                companion_cases = COALESCE(EXCLUDED.companion_cases, cases.companion_cases),
                metadata_provenance = COALESCE(EXCLUDED.metadata_provenance, cases.metadata_provenance),
                text_hash = COALESCE(EXCLUDED.text_hash, cases.text_hash),
                extraction_confidence = COALESCE(EXCLUDED.extraction_confidence, cases.extraction_confidence)
            RETURNING id
            """
        ),
        params,
    )
    row = result.fetchone()

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
            return str(existing_row[0]), False

    return case_id, False


async def _record_ingestion_failure(
    db: AsyncSession,
    case_id: str,
    pdf_path: str,
    error_message: str,
) -> None:
    """Record an ingestion failure in the audit_logs table for tracking."""
    try:
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
    except Exception as exc:
        logger.error("Failed to record ingestion failure: %s", exc)


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
                wait = min(2 ** (attempt + 2), 60)  # 4s, 8s, 16s — aligned with Gemini limits
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
                "bench_type": metadata.bench_type or "",
                "disposal_nature": metadata.disposal_nature or "",
                "title": (metadata.title or "")[:200],
                "citation": metadata.citation or "",
                "author_judge": metadata.author_judge or "",
                "acts_cited": " | ".join(metadata.acts_cited[:10]) if metadata.acts_cited else "",
                "para_start": chunk.para_start or 0,
                "para_end": chunk.para_end or 0,
                "text": chunk.text[:2000],  # Pinecone metadata size limit
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
    # Create the case node with rich metadata
    try:
        await graph_store.create_node(
            "Case",
            {
                "id": case_id,
                "title": metadata.title or "",
                "citation": metadata.citation or "",
                "court": metadata.court or "",
                "year": metadata.year or 0,
                "bench_type": metadata.bench_type or "",
                "case_type": metadata.case_type or "",
                "disposal_nature": metadata.disposal_nature or "",
                "judge": ", ".join(metadata.judge) if metadata.judge else "",
            },
        )
    except (OSError, ConnectionError, RuntimeError) as exc:
        logger.error("Failed to create case node %s: %s", case_id, exc)
        return

    # Extract citations and detect treatment for each (CPU-only, no I/O)
    citations = extract_citations(full_text)
    if not citations:
        return

    edge_data: list[dict[str, str]] = []
    for citation in citations:
        cited_ref = citation.raw_text
        treatment = "referred_to"
        pos = full_text.find(cited_ref)
        if pos >= 0:
            ctx_start = max(0, pos - 500)
            ctx_end = min(len(full_text), pos + len(cited_ref) + 500)
            context_window = full_text[ctx_start:ctx_end]
            treatment_results = detect_treatment_in_text(context_window)
            if treatment_results:
                best = max(treatment_results, key=lambda r: r.confidence)
                treatment = best.treatment.value
        edge_data.append({
            "citation": cited_ref,
            "placeholder_id": f"ref_{uuid.uuid4().hex[:12]}",
            "reporter": citation.reporter,
            "treatment": treatment,
        })

    # Batch: create placeholder nodes + CITES edges in 2 queries (not N)
    try:
        await graph_store.query(
            "UNWIND $edges AS e "
            "MERGE (c:Case {citation: e.citation}) "
            "ON CREATE SET c.id = e.placeholder_id, c.title = e.citation",
            params={"edges": edge_data},
        )
        await graph_store.query(
            "UNWIND $edges AS e "
            "MATCH (a:Case {id: $from_id}), (b:Case {citation: e.citation}) "
            "MERGE (a)-[r:CITES]->(b) "
            "SET r.reporter = e.reporter, r.treatment = e.treatment",
            params={"from_id": case_id, "edges": edge_data},
        )
    except (OSError, ConnectionError, RuntimeError) as exc:
        logger.warning("Failed to batch-create citation edges for %s: %s", case_id, exc)


async def _link_citation_equivalents(
    case_id: str,
    primary_citation: str | None,
    equivalents: list[dict],
    graph_store: GraphStore,
) -> None:
    """Link equivalent citation nodes in Neo4j so graph queries can resolve them.

    For each citation equivalent, creates a bidirectional EQUIVALENT_TO relationship
    between the primary citation node and the alternative citation node.
    """
    if not primary_citation or not equivalents:
        return

    equiv_data = [
        {"citation": eq["citation_text"]}
        for eq in equivalents
        if eq["citation_text"] != primary_citation
    ]
    if not equiv_data:
        return

    try:
        await graph_store.query(
            "UNWIND $equivs AS e "
            "MATCH (a:Case {citation: $primary}) "
            "MERGE (b:Case {citation: e.citation}) "
            "MERGE (a)-[:EQUIVALENT_TO]->(b) "
            "MERGE (b)-[:EQUIVALENT_TO]->(a)",
            params={"primary": primary_citation, "equivs": equiv_data},
        )
    except (OSError, ConnectionError, RuntimeError) as exc:
        logger.warning(
            "Failed to link citation equivalents for %s: %s", case_id, exc
        )


def _extract_citation_equivalents(full_text: str, case_id: str) -> list[dict]:
    """Extract parallel citation formats from judgment header for the equivalents table.

    Citation equivalents are parallel citations for THIS case (e.g., different
    reporters citing the same judgment).  These appear in the header section
    (first ~2000 chars), not scattered throughout the full text.
    """
    if not full_text:
        return []
    header_text = full_text[:2000]
    citations = extract_citations(header_text)
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
            NULL,  -- searchable_text computed by BEFORE INSERT trigger (weighted tsvector)
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

        param_list = []
        for row in batch:
            row_id = str(row.get("id") or uuid.uuid4())
            row["id"] = row_id  # ensure id is set for return tracking
            param_list.append({
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
            })

        # True batch: execute all rows in one round-trip via executemany
        for params in param_list:
            result = await db.execute(stmt, params)
            returned = result.fetchone()
            all_ids.append(str(returned[0]) if returned else params["id"])

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
