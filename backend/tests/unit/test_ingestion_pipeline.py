"""Tests for the ingestion pipeline orchestrator.

Covers full pipeline orchestration, error handling for PDF parsing and
embedding failures, empty text handling, and chunking configuration.
"""

from __future__ import annotations

import os

# Mock embedder uses 4-dim vectors; tell pipeline to accept them
os.environ.setdefault("EMBEDDING_DIMENSION", "4")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.ingestion.chunker import Chunk, Section
from app.core.ingestion.metadata import CaseMetadata
from app.core.ingestion.pipeline import (
    _EMBED_BATCH_SIZE,
    _build_citation_graph,
    _embed_chunks,
    _safe_filename,
    ingest_judgment,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LONG_TEXT = "A" * 200  # text > 100 chars to pass extraction threshold


def _make_case_metadata(**overrides) -> CaseMetadata:
    defaults = {
        "title": "State v. Kumar",
        "citation": "(2023) 5 SCC 123",
        "court": "Supreme Court of India",
        "judge": ["Justice Sharma"],
        "author_judge": "Justice Sharma",
        "year": 2023,
        "decision_date": "2023-03-15",
        "case_type": "Civil Appeal",
        "bench_type": "Division Bench",
        "jurisdiction": "Civil",
        "petitioner": "State of Maharashtra",
        "respondent": "Rajesh Kumar",
        "ratio_decidendi": "Personal hearing is mandatory under Section 26",
        "acts_cited": ["Land Acquisition Act, 2013"],
        "cases_cited": ["(2019) 5 SCC 234"],
        "keywords": ["land acquisition"],
        "disposal_nature": "Dismissed",
    }
    defaults.update(overrides)
    return CaseMetadata(**defaults)


def _make_chunks(n: int = 3, case_id: str = "test-case-id") -> list[Chunk]:
    return [
        Chunk(
            text=f"Chunk text {i}",
            section_type="ANALYSIS",
            chunk_index=i,
            case_id=case_id,
        )
        for i in range(n)
    ]


def _make_sections() -> list[Section]:
    return [
        Section(type="HEADER", start=0, end=50, text="IN THE SUPREME COURT..."),
        Section(type="FACTS", start=50, end=150, text="Facts of the case..."),
    ]


def _make_embeddings(n: int = 3) -> list[list[float]]:
    """Return n dummy 4-dimensional embeddings."""
    return [[0.1 * i, 0.2 * i, 0.3 * i, 0.4 * i] for i in range(n)]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock async DB session."""
    db = AsyncMock()
    # Make execute return a mock with scalar_one_or_none / fetchone
    result = MagicMock()
    result.fetchone.return_value = None
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    # Support async with db.begin_nested(): (used for status update savepoint)
    # db.begin_nested() is a sync call returning an async context manager
    mock_begin = MagicMock()
    mock_begin.__aenter__ = AsyncMock(return_value=mock_begin)
    mock_begin.__aexit__ = AsyncMock(return_value=False)
    db.begin_nested = MagicMock(return_value=mock_begin)
    return db


@pytest.fixture
def mock_llm() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_embedder() -> AsyncMock:
    embedder = AsyncMock()
    embedder.embed_batch.return_value = _make_embeddings(3)
    embedder.dimension = 4
    return embedder


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_graph_store() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_storage() -> AsyncMock:
    storage = AsyncMock()
    storage.store.return_value = "cases/test-id/judgment.pdf"
    return storage


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIngestJudgment:
    """Tests for the full ingest_judgment pipeline."""

    @patch("app.core.ingestion.pipeline._build_citation_graph", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline._upsert_vectors", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline._embed_chunks", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline.chunk_judgment")
    @patch("app.core.ingestion.pipeline.detect_judgment_sections")
    @patch("app.core.ingestion.pipeline._insert_case", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline.cross_validate_propositions")
    @patch("app.core.ingestion.pipeline.validate_cross_fields")
    @patch("app.core.ingestion.pipeline.validate_with_regex")
    @patch("app.core.ingestion.pipeline.merge_metadata")
    @patch("app.core.ingestion.pipeline.extract_metadata_llm", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline.extract_and_score", new_callable=AsyncMock)
    async def test_pipeline_processes_document(
        self,
        mock_extract_and_score: AsyncMock,
        mock_extract_meta_llm: AsyncMock,
        mock_merge_meta: MagicMock,
        mock_validate: MagicMock,
        mock_validate_cross: MagicMock,
        mock_cross_validate_props: MagicMock,
        mock_insert_case: AsyncMock,
        mock_detect_sections: MagicMock,
        mock_chunk: MagicMock,
        mock_embed_chunks: AsyncMock,
        mock_upsert: AsyncMock,
        mock_build_graph: AsyncMock,
        mock_db: AsyncMock,
        mock_llm: AsyncMock,
        mock_embedder: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_graph_store: AsyncMock,
        mock_storage: AsyncMock,
    ) -> None:
        """Full pipeline runs all steps: extract, metadata, chunk, embed, store."""
        from app.core.ingestion.pdf import TextQuality

        metadata = _make_case_metadata()
        chunks = _make_chunks()
        embeddings = _make_embeddings()

        mock_extract_and_score.return_value = TextQuality(
            text=_LONG_TEXT, char_count=len(_LONG_TEXT), tier="high",
            ocr_used=False, legal_keyword_count=5, page_count=10,
        )
        mock_extract_meta_llm.return_value = metadata
        mock_merge_meta.return_value = (metadata, {"title": "parquet"})
        mock_validate.return_value = metadata
        mock_validate_cross.return_value = metadata
        mock_cross_validate_props.return_value = metadata
        mock_insert_case.return_value = ("case-id-123", False)
        mock_detect_sections.return_value = _make_sections()
        mock_chunk.return_value = chunks
        mock_embed_chunks.return_value = embeddings

        parquet_meta = {"title": "Test Case", "path": "s3://bucket/test.pdf"}

        case_id = await ingest_judgment(
            pdf_path="/tmp/test.pdf",
            parquet_metadata=parquet_meta,
            db=mock_db,
            llm=mock_llm,
            embedder=mock_embedder,
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            storage=mock_storage,
        )

        # Verify all pipeline steps were called
        mock_extract_and_score.assert_called_once_with("/tmp/test.pdf")
        mock_extract_meta_llm.assert_called_once()
        mock_merge_meta.assert_called_once()
        mock_validate.assert_called_once()
        mock_validate_cross.assert_called_once()
        mock_cross_validate_props.assert_called_once()
        mock_detect_sections.assert_called_once_with(_LONG_TEXT)
        mock_chunk.assert_called_once()
        # V3: _embed_chunks called once for chunks, possibly again for proposition vectors
        assert mock_embed_chunks.call_count >= 1
        mock_upsert.assert_called_once()
        mock_build_graph.assert_called_once()
        mock_storage.store.assert_called_once()
        assert case_id == "case-id-123"

    @patch("app.core.ingestion.pipeline._record_ingestion_failure", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline.extract_and_score", new_callable=AsyncMock)
    async def test_pipeline_handles_pdf_parse_failure(
        self,
        mock_extract_and_score: AsyncMock,
        mock_record_failure: AsyncMock,
        mock_db: AsyncMock,
        mock_llm: AsyncMock,
        mock_embedder: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_graph_store: AsyncMock,
        mock_storage: AsyncMock,
    ) -> None:
        """Pipeline records failure and returns case_id when PDF yields no text."""
        from app.core.ingestion.pdf import TextQuality

        mock_extract_and_score.return_value = TextQuality(
            text="", char_count=0, tier="low",
            ocr_used=True, legal_keyword_count=0, page_count=0,
        )

        case_id = await ingest_judgment(
            pdf_path="/tmp/corrupt.pdf",
            parquet_metadata={"title": "Corrupt"},
            db=mock_db,
            llm=mock_llm,
            embedder=mock_embedder,
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            storage=mock_storage,
        )

        # Should record the failure
        mock_record_failure.assert_called_once()
        # _record_ingestion_failure(case_id, pdf_path, error_message)
        call_args = mock_record_failure.call_args[0]
        assert call_args[1] == "/tmp/corrupt.pdf"
        assert call_args[2] == "No text extracted"
        # Returns None on extraction failure
        assert case_id is None

    @patch("app.core.ingestion.pipeline._build_citation_graph", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline._upsert_vectors", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline._embed_chunks", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline.chunk_judgment")
    @patch("app.core.ingestion.pipeline.detect_judgment_sections")
    @patch("app.core.ingestion.pipeline._insert_case", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline.validate_cross_fields")
    @patch("app.core.ingestion.pipeline.validate_with_regex")
    @patch("app.core.ingestion.pipeline.merge_metadata")
    @patch("app.core.ingestion.pipeline.extract_metadata_llm", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline.extract_and_score", new_callable=AsyncMock)
    async def test_pipeline_handles_embedding_failure(
        self,
        mock_extract_and_score: AsyncMock,
        mock_extract_meta_llm: AsyncMock,
        mock_merge_meta: MagicMock,
        mock_validate: MagicMock,
        mock_validate_cross: MagicMock,
        mock_insert_case: AsyncMock,
        mock_detect_sections: MagicMock,
        mock_chunk: MagicMock,
        mock_embed_chunks: AsyncMock,
        mock_upsert: AsyncMock,
        mock_build_graph: AsyncMock,
        mock_db: AsyncMock,
        mock_llm: AsyncMock,
        mock_embedder: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_graph_store: AsyncMock,
        mock_storage: AsyncMock,
    ) -> None:
        """Pipeline propagates embedding failures as exceptions."""
        from app.core.ingestion.pdf import TextQuality

        metadata = _make_case_metadata()

        mock_extract_and_score.return_value = TextQuality(
            text=_LONG_TEXT, char_count=len(_LONG_TEXT), tier="high",
            ocr_used=False, legal_keyword_count=5, page_count=10,
        )
        mock_extract_meta_llm.return_value = metadata
        mock_merge_meta.return_value = (metadata, {"title": "parquet"})
        mock_validate.return_value = metadata
        mock_validate_cross.return_value = metadata
        mock_insert_case.return_value = ("case-id-123", False)
        mock_detect_sections.return_value = _make_sections()
        mock_chunk.return_value = _make_chunks()

        # Embedding step raises an exception
        mock_embed_chunks.side_effect = RuntimeError("Embedding service unavailable")

        with pytest.raises(RuntimeError, match="Embedding service unavailable"):
            await ingest_judgment(
                pdf_path="/tmp/test.pdf",
                parquet_metadata={"title": "Test"},
                db=mock_db,
                llm=mock_llm,
                embedder=mock_embedder,
                vector_store=mock_vector_store,
                graph_store=mock_graph_store,
                storage=mock_storage,
            )

    @patch("app.core.ingestion.pipeline._record_ingestion_failure", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline.extract_and_score", new_callable=AsyncMock)
    async def test_pipeline_handles_empty_text(
        self,
        mock_extract_and_score: AsyncMock,
        mock_record_failure: AsyncMock,
        mock_db: AsyncMock,
        mock_llm: AsyncMock,
        mock_embedder: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_graph_store: AsyncMock,
        mock_storage: AsyncMock,
    ) -> None:
        """Pipeline handles empty text: short text from both extractors."""
        from app.core.ingestion.pdf import TextQuality

        mock_extract_and_score.return_value = TextQuality(
            text="Also short", char_count=10, tier="low",
            ocr_used=True, legal_keyword_count=0, page_count=1,
        )

        case_id = await ingest_judgment(
            pdf_path="/tmp/empty.pdf",
            parquet_metadata={"title": "Empty"},
            db=mock_db,
            llm=mock_llm,
            embedder=mock_embedder,
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            storage=mock_storage,
        )

        # Should NOT proceed to metadata extraction or chunking
        mock_embedder.embed_batch.assert_not_called()
        mock_record_failure.assert_called_once()
        assert case_id is None

    @patch("app.core.ingestion.pipeline._build_citation_graph", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline._upsert_vectors", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline._embed_chunks", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline.chunk_judgment")
    @patch("app.core.ingestion.pipeline.detect_judgment_sections")
    @patch("app.core.ingestion.pipeline._insert_case", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline.validate_cross_fields")
    @patch("app.core.ingestion.pipeline.validate_with_regex")
    @patch("app.core.ingestion.pipeline.merge_metadata")
    @patch("app.core.ingestion.pipeline.extract_metadata_llm", new_callable=AsyncMock)
    @patch("app.core.ingestion.pipeline.extract_and_score", new_callable=AsyncMock)
    async def test_chunking_is_called_with_correct_params(
        self,
        mock_extract_and_score: AsyncMock,
        mock_extract_meta_llm: AsyncMock,
        mock_merge_meta: MagicMock,
        mock_validate: MagicMock,
        mock_validate_cross: MagicMock,
        mock_insert_case: AsyncMock,
        mock_detect_sections: MagicMock,
        mock_chunk: MagicMock,
        mock_embed_chunks: AsyncMock,
        mock_upsert: AsyncMock,
        mock_build_graph: AsyncMock,
        mock_db: AsyncMock,
        mock_llm: AsyncMock,
        mock_embedder: AsyncMock,
        mock_vector_store: AsyncMock,
        mock_graph_store: AsyncMock,
        mock_storage: AsyncMock,
    ) -> None:
        """chunk_judgment receives full_text, detected sections, and case_id."""
        from app.core.ingestion.pdf import TextQuality

        metadata = _make_case_metadata()
        sections = _make_sections()
        chunks = _make_chunks()

        mock_extract_and_score.return_value = TextQuality(
            text=_LONG_TEXT, char_count=len(_LONG_TEXT), tier="high",
            ocr_used=False, legal_keyword_count=5, page_count=10,
        )
        mock_extract_meta_llm.return_value = metadata
        mock_merge_meta.return_value = (metadata, {"title": "parquet"})
        mock_validate.return_value = metadata
        mock_validate_cross.return_value = metadata
        mock_insert_case.return_value = ("case-id-456", False)
        mock_detect_sections.return_value = sections
        mock_chunk.return_value = chunks
        mock_embed_chunks.return_value = _make_embeddings()

        await ingest_judgment(
            pdf_path="/tmp/test.pdf",
            parquet_metadata={"title": "Test"},
            db=mock_db,
            llm=mock_llm,
            embedder=mock_embedder,
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
            storage=mock_storage,
        )

        # Verify chunk_judgment was called with the right arguments
        mock_chunk.assert_called_once_with(
            _LONG_TEXT,
            sections,
            case_id="case-id-456",
        )

        # detect_judgment_sections receives the full text
        mock_detect_sections.assert_called_once_with(_LONG_TEXT)


class TestEmbedChunks:
    """Tests for the _embed_chunks helper."""

    async def test_embed_chunks_batches_correctly(self) -> None:
        """Embeddings are requested in batches of _EMBED_BATCH_SIZE."""
        # Create more chunks than one batch
        n_chunks = _EMBED_BATCH_SIZE + 5
        chunks = _make_chunks(n=n_chunks)

        mock_embedder = AsyncMock()
        # Return matching number of embeddings per batch
        mock_embedder.embed_batch.side_effect = [
            _make_embeddings(n=_EMBED_BATCH_SIZE),
            _make_embeddings(n=5),
        ]

        result = await _embed_chunks(chunks, mock_embedder)

        assert len(result) == n_chunks
        assert mock_embedder.embed_batch.call_count == 2
        # First batch should have _EMBED_BATCH_SIZE texts
        first_call_texts = mock_embedder.embed_batch.call_args_list[0][0][0]
        assert len(first_call_texts) == _EMBED_BATCH_SIZE
        # Second batch has the remainder
        second_call_texts = mock_embedder.embed_batch.call_args_list[1][0][0]
        assert len(second_call_texts) == 5

    async def test_embed_chunks_empty_list(self) -> None:
        """Empty chunk list returns empty embeddings."""
        mock_embedder = AsyncMock()
        result = await _embed_chunks([], mock_embedder)
        assert result == []
        mock_embedder.embed_batch.assert_not_called()


class TestSafeFilename:
    """Tests for the _safe_filename helper."""

    def test_safe_filename_normal(self) -> None:
        result = _safe_filename({"title": "State v. Kumar (2023)"})
        assert result.endswith(".pdf")
        assert "/" not in result

    def test_safe_filename_empty_title(self) -> None:
        result = _safe_filename({})
        assert result == "unknown.pdf"

    def test_safe_filename_long_title_truncated(self) -> None:
        result = _safe_filename({"title": "A" * 200})
        # Should be truncated to 80 chars + ".pdf"
        assert len(result) <= 85


class TestPlaceholderResolution:
    """Test that ingesting a real case promotes matching placeholder nodes."""

    @pytest.mark.asyncio
    async def test_placeholder_promoted_when_citation_matches(self) -> None:
        """When a placeholder exists with matching citation, promote it in-place."""
        graph_store = AsyncMock()
        # Call sequence: 1) placeholder query (found), 2) ID sync check,
        # 3) placeholder MERGE, 4) CITES edges,
        # 5) cited_by_count targets, 6) cited_by_count self
        graph_store.query = AsyncMock(side_effect=[
            [{"id": "ref_abc123"}],  # placeholder found and promoted
            [{"nid": "real-uuid"}],  # Neo4j-PG ID sync verification
            [],  # placeholder MERGE for cited nodes
            [],  # CITES edge creation
            [],  # cited_by_count for targets
            [],  # cited_by_count for self
        ])
        graph_store.create_node = AsyncMock()

        metadata = _make_case_metadata(
            citation="(2020) 1 SCC 100",
            title="Promoted Case",
        )
        await _build_citation_graph(
            "real-uuid", metadata, "As held in AIR 2010 SC 200, the law is settled.", graph_store,
        )

        # create_node should NOT be called — placeholder was promoted
        graph_store.create_node.assert_not_called()
        # First query should be the placeholder resolution query
        first_cypher = graph_store.query.call_args_list[0].args[0] if graph_store.query.call_args_list[0].args else graph_store.query.call_args_list[0].kwargs.get("cypher", "")
        assert "STARTS WITH 'ref_'" in first_cypher

    @pytest.mark.asyncio
    async def test_no_placeholder_creates_node_normally(self) -> None:
        """When no placeholder exists, create node via create_node."""
        graph_store = AsyncMock()
        graph_store.query = AsyncMock(side_effect=[
            [],  # no placeholder found
            [{"nid": "real-uuid"}],  # Neo4j-PG ID sync verification
            [],  # placeholder MERGE for cited nodes
            [],  # CITES edge creation
            [],  # cited_by_count for targets
            [],  # cited_by_count for self
        ])
        graph_store.create_node = AsyncMock()

        metadata = _make_case_metadata(citation="(2020) 1 SCC 100", title="New Case")
        await _build_citation_graph(
            "real-uuid", metadata, "As held in AIR 2010 SC 200, the law is settled.", graph_store,
        )

        # create_node SHOULD be called
        graph_store.create_node.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_citation_skips_placeholder_check(self) -> None:
        """When metadata has no citation, skip placeholder check entirely."""
        graph_store = AsyncMock()
        graph_store.query = AsyncMock(return_value=[])
        graph_store.create_node = AsyncMock()

        metadata = _make_case_metadata(citation="", title="No Citation Case")
        await _build_citation_graph(
            "real-uuid", metadata, "Short text with no citations.", graph_store,
        )

        # create_node should be called (no placeholder check)
        graph_store.create_node.assert_called_once()


class TestGraphPropertyPersistence:
    """Test that cited_by_count and is_overruled are persisted during ingestion."""

    @pytest.mark.asyncio
    async def test_is_overruled_in_cites_query(self) -> None:
        """CITES edge creation query should include is_overruled logic."""
        graph_store = AsyncMock()
        graph_store.query = AsyncMock(return_value=[])
        graph_store.create_node = AsyncMock()

        metadata = _make_case_metadata(citation="(2022) 1 SCC 1", title="Overruling Case")
        full_text = "The decision in AIR 2010 SC 100 is hereby overruled by this bench."

        await _build_citation_graph("case-uuid", metadata, full_text, graph_store)

        # Find the CITES edge creation query
        all_cyphers = [
            c.args[0] if c.args else c.kwargs.get("cypher", "")
            for c in graph_store.query.call_args_list
        ]
        cites_queries = [q for q in all_cyphers if "MERGE (a)-[r:CITES]->(b)" in q]
        assert len(cites_queries) >= 1, f"Expected CITES query, got: {all_cyphers}"
        assert "is_overruled" in cites_queries[0]

    @pytest.mark.asyncio
    async def test_cited_by_count_updated_after_edges(self) -> None:
        """After creating CITES edges, cited_by_count should be computed."""
        graph_store = AsyncMock()
        graph_store.query = AsyncMock(return_value=[])
        graph_store.create_node = AsyncMock()

        metadata = _make_case_metadata(citation="(2022) 1 SCC 1", title="Citing Case")
        full_text = "As held in AIR 2010 SC 100, the principle applies."

        await _build_citation_graph("case-uuid", metadata, full_text, graph_store)

        all_cyphers = [
            c.args[0] if c.args else c.kwargs.get("cypher", "")
            for c in graph_store.query.call_args_list
        ]
        count_queries = [q for q in all_cyphers if "cited_by_count" in q]
        assert len(count_queries) >= 1, f"Expected cited_by_count query, got: {all_cyphers}"
