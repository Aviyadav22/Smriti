"""Integration tests for the ingestion pipeline.

Tests the full ingest_judgment pipeline and helper functions with all
external services (DB, LLM, embedder, vector store, graph store, storage)
mocked out.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.ingestion.chunker import Chunk
from app.core.ingestion.metadata import CaseMetadata
from app.core.ingestion.pipeline import (
    _EMBED_BATCH_SIZE,
    _embed_chunks,
    _safe_filename,
    ingest_judgment,
)


# ---------------------------------------------------------------------------
# Helpers for building mocks
# ---------------------------------------------------------------------------

def _make_db_mock(*, existing_citation_id: str | None = None) -> AsyncMock:
    """Build an AsyncMock that behaves like an async SQLAlchemy session.

    Args:
        existing_citation_id: If set, the SELECT for duplicate citation
            will return this id. Otherwise it returns no rows.
    """
    db = AsyncMock()

    # We need db.execute to return different things depending on the SQL.
    # Use a side_effect function to inspect the SQL text.
    async def _execute_side_effect(stmt, params=None):
        sql = str(stmt.text) if hasattr(stmt, "text") else str(stmt)
        result = MagicMock()

        if "SELECT id FROM cases WHERE citation" in sql:
            if existing_citation_id:
                row = MagicMock()
                row.__getitem__ = lambda self, idx: existing_citation_id
                result.fetchone.return_value = row
            else:
                result.fetchone.return_value = None
        else:
            result.fetchone.return_value = None

        return result

    db.execute = AsyncMock(side_effect=_execute_side_effect)
    db.commit = AsyncMock()
    return db


def _make_llm_mock() -> AsyncMock:
    """Build an AsyncMock LLMProvider that returns realistic metadata."""
    llm = AsyncMock()
    llm.generate_structured = AsyncMock(return_value={
        "title": "State of Maharashtra v. Rajesh Kumar",
        "citation": "(2023) 7 SCC 456",
        "court": "Supreme Court of India",
        "judge": ["A.B. Sharma", "C.D. Patel"],
        "year": 2023,
        "decision_date": "2023-03-15",
        "case_type": "Civil Appeal",
        "bench_type": "division",
        "jurisdiction": "civil",
        "petitioner": "State of Maharashtra",
        "respondent": "Rajesh Kumar & Ors.",
        "ratio_decidendi": "Personal hearing under Section 26 is mandatory.",
        "acts_cited": ["Land Acquisition Act, 2013"],
        "cases_cited": ["(2019) 5 SCC 234", "AIR 2020 SC 1567"],
        "keywords": ["land acquisition", "personal hearing", "Section 26"],
        "disposal_nature": "Dismissed",
    })
    return llm


def _make_embedder_mock(dimension: int = 768) -> AsyncMock:
    """Build an AsyncMock EmbeddingProvider."""
    embedder = AsyncMock()
    embedder.embed_batch = AsyncMock(
        side_effect=lambda texts: [[0.1] * dimension for _ in texts]
    )
    embedder.embed_text = AsyncMock(return_value=[0.1] * dimension)
    embedder.dimension = dimension
    return embedder


def _make_vector_store_mock() -> AsyncMock:
    vs = AsyncMock()
    vs.upsert = AsyncMock(return_value=None)
    return vs


def _make_graph_store_mock() -> AsyncMock:
    gs = AsyncMock()
    gs.create_node = AsyncMock(return_value="node-id")
    gs.query = AsyncMock(return_value=[])
    return gs


def _make_storage_mock(case_id: str = "test-case-id") -> AsyncMock:
    storage = AsyncMock()
    storage.store = AsyncMock(return_value=f"cases/{case_id}/judgment.pdf")
    return storage


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestIngestJudgment:
    """Integration tests for the ingest_judgment pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_success(
        self, sample_judgment_text: str, sample_parquet_metadata: dict
    ):
        """Mock all deps and verify the pipeline calls each service correctly."""
        db = _make_db_mock()
        llm = _make_llm_mock()
        embedder = _make_embedder_mock()
        vector_store = _make_vector_store_mock()
        graph_store = _make_graph_store_mock()
        storage = _make_storage_mock()

        with (
            patch(
                "app.core.ingestion.pipeline.extract_pdf_text",
                new=AsyncMock(return_value=sample_judgment_text),
            ),
            patch(
                "app.core.ingestion.pipeline.extract_metadata_llm",
                new=AsyncMock(return_value=CaseMetadata(
                    ratio_decidendi="Personal hearing is mandatory.",
                    acts_cited=["Land Acquisition Act, 2013"],
                    cases_cited=["(2019) 5 SCC 234"],
                    keywords=["land acquisition"],
                    bench_type="division",
                    jurisdiction="civil",
                )),
            ),
        ):
            case_id = await ingest_judgment(
                pdf_path="/tmp/test.pdf",
                parquet_metadata=sample_parquet_metadata,
                db=db,
                llm=llm,
                embedder=embedder,
                vector_store=vector_store,
                graph_store=graph_store,
                storage=storage,
            )

        # Pipeline returns a UUID string.
        assert isinstance(case_id, str)
        assert len(case_id) == 36  # UUID format

        # Storage was called.
        storage.store.assert_awaited_once()
        call_args = storage.store.call_args
        assert call_args[0][0] == "/tmp/test.pdf"
        assert "cases/" in call_args[0][1]

        # Embedder was called with chunk texts.
        assert embedder.embed_batch.await_count >= 1

        # Vector store received upserted vectors.
        assert vector_store.upsert.await_count >= 1

        # Graph store created the case node.
        graph_store.create_node.assert_awaited()
        node_call = graph_store.create_node.call_args
        assert node_call[0][0] == "Case"
        assert node_call[0][1]["id"] == case_id

        # DB was committed (at least for insert + chunk_count update).
        assert db.commit.await_count >= 2

    @pytest.mark.asyncio
    async def test_pipeline_with_ocr_fallback(
        self, sample_judgment_text: str, sample_parquet_metadata: dict
    ):
        """Test OCR fallback when PDF extraction returns insufficient text."""
        db = _make_db_mock()
        llm = _make_llm_mock()
        embedder = _make_embedder_mock()
        vector_store = _make_vector_store_mock()
        graph_store = _make_graph_store_mock()
        storage = _make_storage_mock()

        mock_pdf_extract = AsyncMock(return_value="short")  # < 100 chars
        mock_ocr_extract = AsyncMock(return_value=sample_judgment_text)

        with (
            patch(
                "app.core.ingestion.pipeline.extract_pdf_text",
                new=mock_pdf_extract,
            ),
            patch(
                "app.core.ingestion.pipeline.extract_with_ocr",
                new=mock_ocr_extract,
            ),
            patch(
                "app.core.ingestion.pipeline.extract_metadata_llm",
                new=AsyncMock(return_value=CaseMetadata()),
            ),
        ):
            case_id = await ingest_judgment(
                pdf_path="/tmp/test.pdf",
                parquet_metadata=sample_parquet_metadata,
                db=db,
                llm=llm,
                embedder=embedder,
                vector_store=vector_store,
                graph_store=graph_store,
                storage=storage,
            )

        # PDF extraction was attempted first.
        mock_pdf_extract.assert_awaited_once_with("/tmp/test.pdf")
        # OCR fallback was invoked because pdfplumber returned too little text.
        mock_ocr_extract.assert_awaited_once_with("/tmp/test.pdf")

        # Pipeline still completed successfully.
        assert isinstance(case_id, str)
        storage.store.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pipeline_records_failure_on_no_text(
        self, sample_parquet_metadata: dict
    ):
        """Verify failure recording when no text can be extracted."""
        db = _make_db_mock()
        llm = _make_llm_mock()
        embedder = _make_embedder_mock()
        vector_store = _make_vector_store_mock()
        graph_store = _make_graph_store_mock()
        storage = _make_storage_mock()

        with (
            patch(
                "app.core.ingestion.pipeline.extract_pdf_text",
                new=AsyncMock(return_value=""),
            ),
            patch(
                "app.core.ingestion.pipeline.extract_with_ocr",
                new=AsyncMock(return_value=""),
            ),
        ):
            case_id = await ingest_judgment(
                pdf_path="/tmp/empty.pdf",
                parquet_metadata=sample_parquet_metadata,
                db=db,
                llm=llm,
                embedder=embedder,
                vector_store=vector_store,
                graph_store=graph_store,
                storage=storage,
            )

        # Pipeline returns a case_id even on failure (for tracking).
        assert isinstance(case_id, str)

        # A failure record was inserted into audit_logs.
        # Find the INSERT INTO audit_logs call.
        audit_call_found = False
        for call in db.execute.call_args_list:
            sql_arg = str(call[0][0])
            if "audit_logs" in sql_arg:
                audit_call_found = True
                params = call[0][1]
                assert params["action"] == "ingestion.failed"
                assert params["resource_type"] == "case"
                assert "No text extracted" in params["metadata"]
                break

        assert audit_call_found, "Expected INSERT INTO audit_logs for failure"
        db.commit.assert_awaited()

        # No downstream services should have been called.
        storage.store.assert_not_awaited()
        embedder.embed_batch.assert_not_awaited()
        vector_store.upsert.assert_not_awaited()
        graph_store.create_node.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_duplicate_citation_skips_insert(
        self, sample_judgment_text: str, sample_parquet_metadata: dict
    ):
        """Verify existing citation returns existing case ID without re-inserting."""
        existing_id = str(uuid.uuid4())
        db = _make_db_mock(existing_citation_id=existing_id)
        llm = _make_llm_mock()
        embedder = _make_embedder_mock()
        vector_store = _make_vector_store_mock()
        graph_store = _make_graph_store_mock()
        storage = _make_storage_mock()

        with (
            patch(
                "app.core.ingestion.pipeline.extract_pdf_text",
                new=AsyncMock(return_value=sample_judgment_text),
            ),
            patch(
                "app.core.ingestion.pipeline.extract_metadata_llm",
                new=AsyncMock(return_value=CaseMetadata()),
            ),
        ):
            case_id = await ingest_judgment(
                pdf_path="/tmp/test.pdf",
                parquet_metadata=sample_parquet_metadata,
                db=db,
                llm=llm,
                embedder=embedder,
                vector_store=vector_store,
                graph_store=graph_store,
                storage=storage,
            )

        # The returned case_id should be the existing one, not a new UUID.
        assert case_id == existing_id

        # The INSERT INTO cases should NOT have been executed (only SELECT).
        for call in db.execute.call_args_list:
            sql_arg = str(call[0][0])
            assert "INSERT INTO cases" not in sql_arg or "audit_logs" in sql_arg, (
                "Expected no INSERT INTO cases for duplicate citation"
            )

    @pytest.mark.asyncio
    async def test_pipeline_stores_pdf(
        self, sample_judgment_text: str, sample_parquet_metadata: dict
    ):
        """Verify storage.store is called with the correct destination path."""
        db = _make_db_mock()
        llm = _make_llm_mock()
        embedder = _make_embedder_mock()
        vector_store = _make_vector_store_mock()
        graph_store = _make_graph_store_mock()
        storage = _make_storage_mock()

        with (
            patch(
                "app.core.ingestion.pipeline.extract_pdf_text",
                new=AsyncMock(return_value=sample_judgment_text),
            ),
            patch(
                "app.core.ingestion.pipeline.extract_metadata_llm",
                new=AsyncMock(return_value=CaseMetadata()),
            ),
        ):
            case_id = await ingest_judgment(
                pdf_path="/data/judgments/test.pdf",
                parquet_metadata=sample_parquet_metadata,
                db=db,
                llm=llm,
                embedder=embedder,
                vector_store=vector_store,
                graph_store=graph_store,
                storage=storage,
            )

        storage.store.assert_awaited_once()
        src_path, dest_path = storage.store.call_args[0]

        # Source path should be the original PDF path.
        assert src_path == "/data/judgments/test.pdf"

        # Destination should follow the pattern: cases/{case_id}/{safe_filename}
        assert dest_path.startswith(f"cases/{case_id}/")
        assert dest_path.endswith(".pdf")
        # The filename should be derived from parquet title.
        assert "State of Maharashtra" in dest_path

    @pytest.mark.asyncio
    async def test_pipeline_creates_chunks_and_embeddings(
        self, sample_judgment_text: str, sample_parquet_metadata: dict
    ):
        """Verify chunking produces chunks and embedder is called for each batch."""
        db = _make_db_mock()
        llm = _make_llm_mock()
        embedder = _make_embedder_mock()
        vector_store = _make_vector_store_mock()
        graph_store = _make_graph_store_mock()
        storage = _make_storage_mock()

        with (
            patch(
                "app.core.ingestion.pipeline.extract_pdf_text",
                new=AsyncMock(return_value=sample_judgment_text),
            ),
            patch(
                "app.core.ingestion.pipeline.extract_metadata_llm",
                new=AsyncMock(return_value=CaseMetadata()),
            ),
        ):
            case_id = await ingest_judgment(
                pdf_path="/tmp/test.pdf",
                parquet_metadata=sample_parquet_metadata,
                db=db,
                llm=llm,
                embedder=embedder,
                vector_store=vector_store,
                graph_store=graph_store,
                storage=storage,
            )

        # Embedder should have been called at least once.
        assert embedder.embed_batch.await_count >= 1

        # Vector store should have received vectors with proper structure.
        assert vector_store.upsert.await_count >= 1
        upsert_call = vector_store.upsert.call_args_list[0]
        vectors = upsert_call[0][0]
        assert len(vectors) > 0

        # Each vector should have id, values, metadata.
        first_vec = vectors[0]
        assert "id" in first_vec
        assert "values" in first_vec
        assert "metadata" in first_vec
        assert first_vec["metadata"]["case_id"] == case_id
        assert "section_type" in first_vec["metadata"]
        assert "text" in first_vec["metadata"]

        # chunk_count was updated in DB.
        update_found = False
        for call in db.execute.call_args_list:
            sql_arg = str(call[0][0])
            if "UPDATE cases SET chunk_count" in sql_arg:
                update_found = True
                params = call[0][1]
                assert params["count"] > 0
                assert params["id"] == case_id
                break
        assert update_found, "Expected UPDATE cases SET chunk_count"

    @pytest.mark.asyncio
    async def test_pipeline_builds_citation_graph(
        self, sample_judgment_text: str, sample_parquet_metadata: dict
    ):
        """Verify Neo4j node and edge creation for the citation graph."""
        db = _make_db_mock()
        llm = _make_llm_mock()
        embedder = _make_embedder_mock()
        vector_store = _make_vector_store_mock()
        graph_store = _make_graph_store_mock()
        storage = _make_storage_mock()

        with (
            patch(
                "app.core.ingestion.pipeline.extract_pdf_text",
                new=AsyncMock(return_value=sample_judgment_text),
            ),
            patch(
                "app.core.ingestion.pipeline.extract_metadata_llm",
                new=AsyncMock(return_value=CaseMetadata()),
            ),
        ):
            case_id = await ingest_judgment(
                pdf_path="/tmp/test.pdf",
                parquet_metadata=sample_parquet_metadata,
                db=db,
                llm=llm,
                embedder=embedder,
                vector_store=vector_store,
                graph_store=graph_store,
                storage=storage,
            )

        # Case node was created.
        graph_store.create_node.assert_awaited_once()
        node_call = graph_store.create_node.call_args
        assert node_call[0][0] == "Case"
        props = node_call[0][1]
        assert props["id"] == case_id
        assert "citation" in props
        assert "court" in props

        # The sample_judgment_text contains citations like:
        # (2019) 5 SCC 234, AIR 2020 SC 1567, 2021 INSC 456,
        # (2018) 3 SCC 789, [2020] 4 SCR 123
        # Each citation triggers a MERGE + CITES edge query pair.
        # graph_store.query is called twice per citation (MERGE placeholder + CITES edge).
        assert graph_store.query.await_count >= 2, (
            f"Expected at least 2 graph queries for citations, got {graph_store.query.await_count}"
        )

        # Check that at least one CITES edge was created.
        cites_edge_found = False
        for call in graph_store.query.call_args_list:
            cypher = call[0][0]
            if "CITES" in cypher:
                cites_edge_found = True
                params = call[1].get("params", {}) if call[1] else {}
                assert params.get("from_id") == case_id
                break
        assert cites_edge_found, "Expected at least one CITES edge creation"


@pytest.mark.integration
class TestHelperFunctions:
    """Tests for pipeline helper functions."""

    def test_safe_filename_from_title(self):
        """Test filename sanitization from parquet title."""
        meta = {"title": "State of Maharashtra v. Rajesh Kumar & Ors."}
        result = _safe_filename(meta)
        assert result.endswith(".pdf")
        # Special chars like '&' and '.' should be stripped or kept per the logic.
        assert "/" not in result
        assert "\\" not in result
        # Alphanumeric and basic punctuation are preserved.
        assert "State of Maharashtra" in result

    def test_safe_filename_special_characters(self):
        """Test that unsafe characters are stripped from filename."""
        meta = {"title": "A/B\\C:D*E?F\"G<H>I|J"}
        result = _safe_filename(meta)
        assert result.endswith(".pdf")
        # None of the unsafe characters should remain.
        for ch in "/\\:*?\"<>|":
            assert ch not in result

    def test_safe_filename_empty(self):
        """Test empty/missing title fallback."""
        # Missing title key falls back to "unknown" default.
        result = _safe_filename({})
        assert result == "unknown.pdf"

        # Empty title produces the "judgment.pdf" fallback
        # because the safe string is empty after stripping.
        result = _safe_filename({"title": ""})
        assert result == "judgment.pdf"

        # Title with only special chars also falls back.
        result = _safe_filename({"title": "///***"})
        assert result == "judgment.pdf"

    def test_safe_filename_long_title_truncated(self):
        """Test that very long titles are truncated to 80 chars + .pdf."""
        meta = {"title": "A" * 200}
        result = _safe_filename(meta)
        # Should be at most 80 chars of title + ".pdf" (4 chars) = 84
        assert len(result) <= 84
        assert result.endswith(".pdf")

    @pytest.mark.asyncio
    async def test_embed_chunks_batching(self):
        """Verify that _embed_chunks batches at _EMBED_BATCH_SIZE."""
        embedder = _make_embedder_mock(dimension=768)

        # Create more chunks than one batch.
        num_chunks = _EMBED_BATCH_SIZE + 5
        chunks = [
            Chunk(
                text=f"Chunk text number {i}",
                section_type="FULL",
                chunk_index=i,
                case_id="test-case",
            )
            for i in range(num_chunks)
        ]

        embeddings = await _embed_chunks(chunks, embedder)

        # Should return one embedding per chunk.
        assert len(embeddings) == num_chunks

        # Embedder should have been called exactly 2 times:
        # batch 1: _EMBED_BATCH_SIZE items, batch 2: 5 items.
        assert embedder.embed_batch.await_count == 2

        # Verify first batch size.
        first_batch = embedder.embed_batch.call_args_list[0][0][0]
        assert len(first_batch) == _EMBED_BATCH_SIZE

        # Verify second batch size.
        second_batch = embedder.embed_batch.call_args_list[1][0][0]
        assert len(second_batch) == 5

    @pytest.mark.asyncio
    async def test_embed_chunks_single_batch(self):
        """Verify that fewer chunks than batch size results in a single call."""
        embedder = _make_embedder_mock(dimension=768)

        chunks = [
            Chunk(
                text=f"Chunk {i}",
                section_type="ANALYSIS",
                chunk_index=i,
                case_id="test-case",
            )
            for i in range(3)
        ]

        embeddings = await _embed_chunks(chunks, embedder)

        assert len(embeddings) == 3
        assert embedder.embed_batch.await_count == 1

    @pytest.mark.asyncio
    async def test_embed_chunks_empty_list(self):
        """Verify that empty chunk list returns empty embeddings."""
        embedder = _make_embedder_mock()

        embeddings = await _embed_chunks([], embedder)

        assert embeddings == []
        embedder.embed_batch.assert_not_awaited()
