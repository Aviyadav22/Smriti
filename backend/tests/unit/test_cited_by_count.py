"""Tests for computed cited_by_count."""

from unittest.mock import AsyncMock

import pytest


class TestComputedCitedByCount:
    """Verify cited_by_count is computed from graph, not stored."""

    @pytest.mark.asyncio
    async def test_get_cited_by_count(self):
        from app.core.ingestion.pipeline import get_cited_by_count

        mock_graph = AsyncMock()
        mock_graph.query.return_value = [{"cited_by_count": 42}]

        count = await get_cited_by_count("case-1", mock_graph)
        assert count == 42

    @pytest.mark.asyncio
    async def test_get_cited_by_count_not_found(self):
        from app.core.ingestion.pipeline import get_cited_by_count

        mock_graph = AsyncMock()
        mock_graph.query.return_value = []

        count = await get_cited_by_count("case-1", mock_graph)
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_cited_by_count_on_error(self):
        from app.core.ingestion.pipeline import get_cited_by_count

        mock_graph = AsyncMock()
        mock_graph.query.side_effect = RuntimeError("Neo4j down")

        count = await get_cited_by_count("case-1", mock_graph)
        assert count == 0
