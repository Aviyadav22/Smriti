"""Tests for PrecedentMapperService."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.analysis.precedent_mapper import PrecedentMapperService
from app.core.search.hybrid import SearchResponse, SearchResultItem
from app.core.search.query import QueryEntities, QueryUnderstanding, SearchFilters


def _make_search_response(n: int = 3) -> SearchResponse:
    return SearchResponse(
        results=[
            SearchResultItem(
                case_id=f"case-{i}",
                score=1.0 - i * 0.1,
                title=f"Case {i} v. State",
                citation=f"(2024) {i} SCC 100",
                court="Supreme Court of India",
                year=2024,
            )
            for i in range(n)
        ],
        total_count=n,
        page=1,
        page_size=10,
        query_understanding=QueryUnderstanding(
            original_query="test",
            intent="general",
            entities=QueryEntities(),
            expanded_query="test",
            filters=SearchFilters(),
            search_strategy="balanced",
        ),
    )


class TestMapPrecedents:
    @pytest.mark.asyncio
    @patch("app.core.analysis.precedent_mapper.hybrid_search")
    async def test_maps_single_issue(self, mock_search: AsyncMock) -> None:
        mock_search.return_value = _make_search_response(3)

        service = PrecedentMapperService(
            llm=AsyncMock(),
            embedder=AsyncMock(),
            vector_store=AsyncMock(),
            reranker=AsyncMock(),
            db=AsyncMock(),
        )

        issues = [{"title": "Right to Privacy", "description": "Whether Article 21 is violated"}]
        results = await service.map_precedents(issues)

        assert len(results) == 1
        assert results[0].issue_title == "Right to Privacy"
        assert len(results[0].supporting) == 3

    @pytest.mark.asyncio
    @patch("app.core.analysis.precedent_mapper.hybrid_search")
    async def test_maps_multiple_issues_in_parallel(self, mock_search: AsyncMock) -> None:
        mock_search.return_value = _make_search_response(2)

        service = PrecedentMapperService(
            llm=AsyncMock(),
            embedder=AsyncMock(),
            vector_store=AsyncMock(),
            reranker=AsyncMock(),
            db=AsyncMock(),
        )

        issues = [
            {"title": "Issue 1", "description": "Desc 1"},
            {"title": "Issue 2", "description": "Desc 2"},
            {"title": "Issue 3", "description": "Desc 3"},
        ]
        results = await service.map_precedents(issues)

        assert len(results) == 3
        assert mock_search.call_count == 3

    @pytest.mark.asyncio
    @patch("app.core.analysis.precedent_mapper.hybrid_search")
    async def test_includes_acts_in_query(self, mock_search: AsyncMock) -> None:
        mock_search.return_value = _make_search_response(1)

        service = PrecedentMapperService(
            llm=AsyncMock(),
            embedder=AsyncMock(),
            vector_store=AsyncMock(),
            reranker=AsyncMock(),
            db=AsyncMock(),
        )

        issues = [{"title": "Tax Evasion", "description": "Under Income Tax Act"}]
        results = await service.map_precedents(
            issues, acts_referenced=["Income Tax Act, 1961"]
        )

        assert results[0].statutes == ["Income Tax Act, 1961"]

    @pytest.mark.asyncio
    @patch("app.core.analysis.precedent_mapper.hybrid_search")
    async def test_handles_search_failure_gracefully(self, mock_search: AsyncMock) -> None:
        mock_search.side_effect = Exception("Search failed")

        service = PrecedentMapperService(
            llm=AsyncMock(),
            embedder=AsyncMock(),
            vector_store=AsyncMock(),
            reranker=AsyncMock(),
            db=AsyncMock(),
        )

        issues = [{"title": "Issue 1", "description": "Desc 1"}]
        results = await service.map_precedents(issues)

        assert len(results) == 1
        assert results[0].supporting == []

    @pytest.mark.asyncio
    @patch("app.core.analysis.precedent_mapper.hybrid_search")
    async def test_respects_max_per_issue(self, mock_search: AsyncMock) -> None:
        mock_search.return_value = _make_search_response(10)

        service = PrecedentMapperService(
            llm=AsyncMock(),
            embedder=AsyncMock(),
            vector_store=AsyncMock(),
            reranker=AsyncMock(),
            db=AsyncMock(),
        )

        issues = [{"title": "Issue 1", "description": "Desc 1"}]
        results = await service.map_precedents(issues, max_per_issue=3)

        assert len(results[0].supporting) == 3
