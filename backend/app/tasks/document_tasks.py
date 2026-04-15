"""Celery task for document analysis pipeline."""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import text

from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def analyze_document(self, document_id: str) -> dict:
    """Run the full document analysis pipeline."""
    import asyncio
    return asyncio.run(_analyze_document_async(document_id))


async def _analyze_document_async(document_id: str) -> dict:
    """Async implementation of the document analysis pipeline."""
    from app.core.analysis.document_analyzer import DocumentAnalyzerService
    from app.core.analysis.precedent_mapper import PrecedentMapperService
    from app.core.providers.document_parsers.pdf_parser import PDFParser
    from app.core.providers.embeddings.gemini import GeminiEmbedder
    from app.core.providers.llm.gemini import GeminiLLM
    from app.core.providers.rerankers.cohere_reranker import CohereReranker
    from app.core.providers.vector.pinecone_store import PineconeStore
    from app.db.postgres import get_async_session

    async with get_async_session() as db:
        try:
            await _update_doc_status(db, document_id, "extracting", "Extracting text from PDF")

            result = await db.execute(
                text("SELECT storage_path, filename FROM documents WHERE id = :id"),
                {"id": document_id},
            )
            doc = result.mappings().one_or_none()
            if not doc:
                raise ValueError(f"Document not found: {document_id}")

            # Step 1: Extract text
            parser = PDFParser()
            extracted_text = await parser.extract_text(doc["storage_path"])
            if not extracted_text or len(extracted_text.strip()) < 50:
                extracted_text = await parser.extract_text_with_ocr(doc["storage_path"])

            # Step 2: Extract issues
            await _update_doc_status(db, document_id, "analyzing", "Identifying legal issues")
            llm = GeminiLLM()
            analyzer = DocumentAnalyzerService(llm)
            extraction = await analyzer.extract_issues(extracted_text)

            # Step 3: Search for precedents
            await _update_doc_status(db, document_id, "searching", "Finding relevant precedents")
            embedder = GeminiEmbedder()
            vector_store = PineconeStore()
            reranker = CohereReranker()

            mapper = PrecedentMapperService(
                llm=llm, embedder=embedder, vector_store=vector_store,
                reranker=reranker, db=db,
            )
            issues_dicts = [
                {"title": i.title, "description": i.description}
                for i in extraction.issues
            ]
            precedent_results = await mapper.map_precedents(
                issues_dicts, acts_referenced=extraction.acts_referenced,
            )

            issues_with_precedents = _format_issues_with_precedents(
                extraction.issues, precedent_results
            )

            # Step 4: Generate counter-arguments
            await _update_doc_status(db, document_id, "generating", "Generating analysis")
            counter_args = await analyzer.generate_counter_arguments(
                extraction.document_type, issues_with_precedents,
            )

            # Step 5: Generate research memo
            counter_args_text = "\n".join(
                f"- {ca.issue_title}: {ca.argument} → {ca.response}"
                for ca in counter_args
            )
            memo = await analyzer.generate_research_memo(
                document_type=extraction.document_type,
                parties=extraction.parties,
                relief_sought=extraction.relief_sought,
                key_facts=extraction.key_facts,
                issues_analysis=issues_with_precedents,
                counter_arguments=counter_args_text,
            )

            # Step 6: Chunk, embed, and index for search
            await _update_doc_status(db, document_id, "indexing", "Indexing for search")
            await _chunk_embed_and_index(
                document_id=document_id,
                extracted_text=extracted_text,
                embedder=embedder,
                vector_store=vector_store,
                db=db,
            )

            # Step 7: Store results
            analysis_id = str(uuid.uuid4())
            issues_json = [
                {
                    "title": issue.title,
                    "description": issue.description,
                    "supporting_precedents": [
                        {"case_id": r.case_id, "title": r.title, "citation": r.citation, "score": r.score}
                        for r in pr.supporting
                    ],
                    "statutes": pr.statutes,
                }
                for issue, pr in zip(extraction.issues, precedent_results, strict=False)
            ]
            counter_args_json = [
                {"issue_title": ca.issue_title, "argument": ca.argument, "response": ca.response}
                for ca in counter_args
            ]

            await db.execute(
                text(
                    "INSERT INTO document_analyses "
                    "(id, document_id, extracted_text, issues, parties, key_facts, "
                    "relief_sought, counter_arguments, research_memo) "
                    "VALUES (:id, :doc_id, :text, :issues, :parties, :facts, "
                    ":relief, :counter, :memo)"
                ),
                {
                    "id": analysis_id,
                    "doc_id": document_id,
                    "text": extracted_text[:50000],
                    "issues": json.dumps(issues_json),
                    "parties": json.dumps(extraction.parties),
                    "facts": "\n".join(extraction.key_facts),
                    "relief": extraction.relief_sought,
                    "counter": json.dumps(counter_args_json),
                    "memo": memo,
                },
            )

            await _update_doc_status(db, document_id, "completed", None, completed=True)
            await db.commit()

            return {"status": "completed", "document_id": document_id, "analysis_id": analysis_id}

        except (ConnectionError, TimeoutError, OSError) as exc:
            logger.warning("Transient error during document analysis: %s", exc)
            await _update_doc_status(db, document_id, "failed", None, error=str(exc))
            await db.commit()
            raise
        except Exception as exc:
            logger.exception("Document analysis failed: %s", document_id)
            await _update_doc_status(db, document_id, "failed", None, error=str(exc))
            await db.commit()
            return {"status": "failed", "document_id": document_id, "error": str(exc)}


async def _update_doc_status(
    db: object,
    document_id: str,
    status: str,
    step: str | None,
    *,
    completed: bool = False,
    error: str | None = None,
) -> None:
    """Update document status and processing step."""
    params: dict = {"id": document_id, "status": status, "step": step}

    if completed and error:
        params["error"] = error
        sql = text(
            "UPDATE documents SET status = :status, processing_step = :step, "
            "updated_at = NOW(), processing_completed_at = NOW(), error_message = :error "
            "WHERE id = :id"
        )
    elif completed:
        sql = text(
            "UPDATE documents SET status = :status, processing_step = :step, "
            "updated_at = NOW(), processing_completed_at = NOW() "
            "WHERE id = :id"
        )
    elif error and status == "extracting":
        params["error"] = error
        sql = text(
            "UPDATE documents SET status = :status, processing_step = :step, "
            "updated_at = NOW(), processing_started_at = NOW(), error_message = :error "
            "WHERE id = :id"
        )
    elif status == "extracting":
        sql = text(
            "UPDATE documents SET status = :status, processing_step = :step, "
            "updated_at = NOW(), processing_started_at = NOW() "
            "WHERE id = :id"
        )
    elif error:
        params["error"] = error
        sql = text(
            "UPDATE documents SET status = :status, processing_step = :step, "
            "updated_at = NOW(), error_message = :error "
            "WHERE id = :id"
        )
    else:
        sql = text(
            "UPDATE documents SET status = :status, processing_step = :step, "
            "updated_at = NOW() "
            "WHERE id = :id"
        )

    await db.execute(sql, params)


async def _chunk_embed_and_index(
    document_id: str,
    extracted_text: str,
    embedder: object,
    vector_store: object,
    db: object,
) -> None:
    """Chunk the document text, embed it, and upsert to vector store.

    This bridges the gap between document upload/analysis and search:
    without this step, uploaded documents would be invisible to semantic
    search and RAG chat.
    """
    from app.core.ingestion.chunker import chunk_judgment, detect_judgment_sections

    sections = detect_judgment_sections(extracted_text)
    chunks = chunk_judgment(extracted_text, sections, case_id=document_id)

    if not chunks:
        logger.warning("No chunks produced for document %s", document_id)
        return

    # Embed in batches of 20 (same as ingestion pipeline)
    _BATCH_SIZE = 20
    all_embeddings: list[list[float]] = []
    for i in range(0, len(chunks), _BATCH_SIZE):
        batch_texts = [c.text for c in chunks[i : i + _BATCH_SIZE]]
        batch_embeddings = await embedder.embed_batch(batch_texts)
        all_embeddings.extend(batch_embeddings)

    # Build vector records and upsert to Pinecone
    vectors: list[dict] = []
    for chunk, embedding in zip(chunks, all_embeddings, strict=False):
        vector_id = f"doc_{document_id}_{chunk.chunk_index}"
        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": {
                "case_id": document_id,
                "chunk_index": chunk.chunk_index,
                "section_type": chunk.section_type,
                "source": "upload",
                "text": chunk.text[:1000],
            },
        })

    for i in range(0, len(vectors), 100):
        await vector_store.upsert(vectors[i : i + 100])

    # Update the document record with chunk count
    await db.execute(
        text("UPDATE documents SET chunk_count = :count WHERE id = :id"),
        {"count": len(chunks), "id": document_id},
    )

    logger.info(
        "Indexed document %s: %d chunks, %d vectors",
        document_id, len(chunks), len(vectors),
    )


def _format_issues_with_precedents(issues: list, precedent_results: list) -> str:
    """Format issues and their precedents as text for LLM consumption."""
    sections = []
    for issue, pr in zip(issues, precedent_results, strict=False):
        section = f"## {issue.title}\n{issue.description}\n\n"
        if pr.supporting:
            section += "### Supporting Precedents:\n"
            for r in pr.supporting:
                section += f"- {r.title} ({r.citation or 'No citation'}) — Score: {r.score:.2f}\n"
        if pr.statutes:
            section += "\n### Relevant Statutes:\n"
            for s in pr.statutes:
                section += f"- {s}\n"
        sections.append(section)
    return "\n\n".join(sections)
