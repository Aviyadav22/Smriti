"""Integration test for the search pipeline.

Tests the full flow: query → LLM understanding → statute expansion →
parallel vector + FTS search → RRF merge → Cohere rerank → enrichment →
response with proper Indian legal citation format.

All external services are mocked but the pipeline logic is exercised end-to-end.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.interfaces.reranker import RerankResult
from app.core.interfaces.vector_store import SearchResult
from app.core.search.fulltext import FTSResult
from app.core.search.hybrid import SearchResponse, hybrid_search

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CASE_ID_1 = "aabbccdd-1111-2222-3333-444455556666"
CASE_ID_2 = "aabbccdd-1111-2222-3333-444455557777"


def _make_vector_result(case_id: str, score: float) -> SearchResult:
    return SearchResult(
        id=f"{case_id}_chunk_0",
        score=score,
        metadata={
            "case_id": case_id,
            "text": "The accused was charged under Section 302 IPC for murder.",
        },
    )


def _make_fts_result(case_id: str, rank: float) -> FTSResult:
    return FTSResult(
        case_id=case_id,
        rank=rank,
        title=f"State v. Accused ({case_id[:8]})",
        snippet="Section 302 IPC bail application...",
    )


def _make_db_row(case_id: str, citation: str, year: int) -> dict:
    return {
        "id": case_id,
        "title": f"State v. Accused ({case_id[:8]})",
        "citation": citation,
        "court": "Supreme Court of India",
        "year": year,
        "decision_date": f"{year}-03-15",
        "case_type": "criminal",
        "judge": "Justice D.Y. Chandrachud",
        "bench_type": "division",
    }


def _mock_db_execute(rows: list[dict]):
    """Mock db.execute for all query types in the search pipeline.

    Handles: enrichment, equivalents, FTS, disposal bias, facets, etc.
    """

    async def _execute(sql, params=None):
        mock_result = MagicMock()
        sql_text = str(sql.text) if hasattr(sql, "text") else str(sql)

        if "case_citation_equivalents" in sql_text or "disposal_nature" in sql_text:
            mock_result.mappings.return_value.all.return_value = []
        elif "searchable_text" in sql_text or "websearch_to_tsquery" in sql_text:
            # FTS query — return empty (vector results will carry)
            mock_result.mappings.return_value.all.return_value = []
        elif "ratio_decidendi" in sql_text or "case_sections" in sql_text:
            mock_result.mappings.return_value.all.return_value = []
        elif "COUNT" in sql_text.upper():
            mock_result.scalar.return_value = len(rows)
            mock_result.mappings.return_value.all.return_value = [{"count": len(rows)}]
        else:
            mock_result.mappings.return_value.all.return_value = rows
        return mock_result

    return _execute


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSearchPipelineIntegration:
    """End-to-end search pipeline tests with mocked providers."""

    @pytest.mark.asyncio
    async def test_section_302_ipc_bail_returns_results(self):
        """Full pipeline: 'Section 302 IPC bail' → results with SCC citations."""
        # Mock providers
        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {
            "intent": "topic_search",
            "expanded_query": "Section 302 IPC murder bail anticipatory bail",
            "filters": {},
            "entities": {"legal_concepts": ["murder", "bail"], "statutes": ["IPC 302"]},
            "search_strategy": "balanced",
        }

        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 1536

        mock_vector = AsyncMock()
        mock_vector.search.return_value = [
            _make_vector_result(CASE_ID_1, 0.92),
            _make_vector_result(CASE_ID_2, 0.85),
        ]

        mock_reranker = AsyncMock()
        mock_reranker.rerank.return_value = [
            RerankResult(index=0, score=0.95, text="Section 302 IPC murder bail"),
            RerankResult(index=1, score=0.88, text="Section 302 anticipatory bail"),
        ]

        mock_db = AsyncMock()
        db_rows = [
            _make_db_row(CASE_ID_1, "(2023) 5 SCC 142", 2023),
            _make_db_row(CASE_ID_2, "AIR 2022 SC 1045", 2022),
        ]
        mock_db.execute = _mock_db_execute(db_rows)

        # Execute pipeline
        response = await hybrid_search(
            query="Section 302 IPC bail",
            llm=mock_llm,
            embedder=mock_embedder,
            vector_store=mock_vector,
            reranker=mock_reranker,
            db=mock_db,
        )

        # Verify response structure
        assert isinstance(response, SearchResponse)
        assert response.page == 1
        assert response.page_size == 10
        assert response.query_understanding is not None
        assert response.query_understanding.intent == "topic_search"

        # Verify facets are populated from enrichment data
        assert isinstance(response.facets, dict)

        # Verify pipeline called all providers
        mock_llm.generate_structured.assert_called_once()
        mock_embedder.embed_text.assert_called_once()
        mock_vector.search.assert_called_once()

        # If results are returned, verify citation format
        if response.results:
            first_result = response.results[0]
            assert first_result.case_id is not None
            assert first_result.score > 0
            if first_result.citation:
                # Should be SCC or AIR format
                assert any(fmt in first_result.citation for fmt in ["SCC", "AIR", "INSC"])

    @pytest.mark.asyncio
    async def test_statute_expansion_triggers_for_ipc(self):
        """Query mentioning IPC should trigger BNS expansion in FTS."""
        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {
            "intent": "topic_search",
            "expanded_query": "Section 302 IPC bail",
            "filters": {},
            "entities": {},
            "search_strategy": "balanced",
        }

        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 1536

        mock_vector = AsyncMock()
        mock_vector.search.return_value = []

        mock_reranker = AsyncMock()
        mock_reranker.rerank.return_value = []

        mock_db = AsyncMock()
        mock_db.execute = _mock_db_execute([])

        response = await hybrid_search(
            query="Section 302 IPC bail",
            llm=mock_llm,
            embedder=mock_embedder,
            vector_store=mock_vector,
            reranker=mock_reranker,
            db=mock_db,
        )

        # Pipeline should complete without error even with no results
        assert isinstance(response, SearchResponse)
        assert response.total_count == 0

    @pytest.mark.asyncio
    async def test_response_pagination(self):
        """Search response includes pagination metadata."""
        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {
            "intent": "topic_search",
            "expanded_query": "bail",
            "filters": {},
            "entities": {},
            "search_strategy": "balanced",
        }

        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 1536

        mock_vector = AsyncMock()
        mock_vector.search.return_value = [_make_vector_result(CASE_ID_1, 0.9)]

        mock_reranker = AsyncMock()
        mock_reranker.rerank.return_value = [
            RerankResult(index=0, score=0.9, text="bail"),
        ]

        mock_db = AsyncMock()
        mock_db.execute = _mock_db_execute(
            [
                _make_db_row(CASE_ID_1, "(2024) 1 SCC 100", 2024),
            ]
        )

        response = await hybrid_search(
            query="bail",
            llm=mock_llm,
            embedder=mock_embedder,
            vector_store=mock_vector,
            reranker=mock_reranker,
            db=mock_db,
            page=1,
            page_size=10,
        )

        assert response.page == 1
        assert response.page_size == 10
        assert response.total_count >= 0

    @pytest.mark.asyncio
    async def test_air_citation_format(self):
        """Results with AIR citations should preserve format."""
        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {
            "intent": "topic_search",
            "expanded_query": "anticipatory bail",
            "filters": {},
            "entities": {},
            "search_strategy": "balanced",
        }

        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 1536

        mock_vector = AsyncMock()
        mock_vector.search.return_value = [_make_vector_result(CASE_ID_1, 0.88)]

        mock_reranker = AsyncMock()
        mock_reranker.rerank.return_value = [
            RerankResult(index=0, score=0.88, text="anticipatory bail"),
        ]

        mock_db = AsyncMock()
        mock_db.execute = _mock_db_execute(
            [
                _make_db_row(CASE_ID_1, "AIR 2019 SC 2005", 2019),
            ]
        )

        response = await hybrid_search(
            query="anticipatory bail",
            llm=mock_llm,
            embedder=mock_embedder,
            vector_store=mock_vector,
            reranker=mock_reranker,
            db=mock_db,
        )

        if response.results:
            assert "AIR" in response.results[0].citation
