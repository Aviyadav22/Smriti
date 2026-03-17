"""Tests for graph-based treatment detection in RAG pipeline."""

import pytest
from unittest.mock import AsyncMock


class TestCheckTreatmentFromGraph:
    """Verify check_treatment_from_graph queries Neo4j correctly."""

    @pytest.mark.asyncio
    async def test_returns_overruled_cases(self):
        from app.core.chat.rag import check_treatment_from_graph

        mock_graph = AsyncMock()
        mock_graph.query.return_value = [
            {"case_id": "c1", "overruled_by": "(2023) 5 SCC 100"},
        ]

        result = await check_treatment_from_graph(["c1", "c2"], mock_graph)
        assert result == {"c1": "(2023) 5 SCC 100"}
        mock_graph.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_overruled(self):
        from app.core.chat.rag import check_treatment_from_graph

        mock_graph = AsyncMock()
        mock_graph.query.return_value = []

        result = await check_treatment_from_graph(["c1"], mock_graph)
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_on_graph_error(self):
        from app.core.chat.rag import check_treatment_from_graph

        mock_graph = AsyncMock()
        mock_graph.query.side_effect = RuntimeError("Neo4j down")

        result = await check_treatment_from_graph(["c1"], mock_graph)
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_input(self):
        from app.core.chat.rag import check_treatment_from_graph

        mock_graph = AsyncMock()
        result = await check_treatment_from_graph([], mock_graph)
        assert result == {}
        mock_graph.query.assert_not_called()
