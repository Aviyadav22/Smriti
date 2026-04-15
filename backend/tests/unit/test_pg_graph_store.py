"""Tests for PgGraphStore — PostgreSQL-based graph store provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.providers.graph.pg_graph_store import (
    PgGraphStore,
    _validate_label,
    _validate_relationship,
)

# ---------------------------------------------------------------------------
# Input validation tests (mirrors test_neo4j_store.py)
# ---------------------------------------------------------------------------


def test_validate_label_accepts_known():
    assert _validate_label("Case") == "Case"
    assert _validate_label("Statute") == "Statute"


def test_validate_label_rejects_unknown():
    with pytest.raises(ValueError, match="Invalid node label"):
        _validate_label("Case) DETACH DELETE n //")


def test_validate_label_rejects_injection():
    with pytest.raises(ValueError):
        _validate_label("Case}-[:HACKED]->(x) DELETE x WITH x MATCH (n:{label:")


def test_validate_relationship_accepts_known():
    assert _validate_relationship("CITES") == "CITES"
    assert _validate_relationship("EQUIVALENT_TO") == "EQUIVALENT_TO"
    assert _validate_relationship("APPLIES_PRINCIPLE") == "APPLIES_PRINCIPLE"


def test_validate_relationship_rejects_injection():
    with pytest.raises(ValueError):
        _validate_relationship("CITES] DETACH DELETE n WITH n MATCH (m)-[r:")


def test_validate_relationship_rejects_unknown():
    with pytest.raises(ValueError, match="Invalid relationship"):
        _validate_relationship("DROP_DATABASE")


# ---------------------------------------------------------------------------
# PgGraphStore unit tests (mocked DB)
# ---------------------------------------------------------------------------


class TestPgGraphStoreCreateNode:
    """Verify create_node for Case labels."""

    @patch("app.core.providers.graph.pg_graph_store.async_session_factory")
    @pytest.mark.asyncio
    async def test_create_case_node_existing(self, mock_factory):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, idx: "case-123"
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_factory.return_value = mock_session

        store = PgGraphStore()
        result = await store.create_node("Case", {"id": "case-123", "citation": "2024 SCC 1"})
        assert result == "case-123"

    @pytest.mark.asyncio
    async def test_create_node_rejects_invalid_label(self):
        store = PgGraphStore()
        with pytest.raises(ValueError, match="Invalid node label"):
            await store.create_node("Evil; DROP TABLE", {"id": "x"})

    @pytest.mark.asyncio
    async def test_create_node_requires_id(self):
        store = PgGraphStore()
        with pytest.raises(ValueError, match="must include 'id'"):
            await store.create_node("Case", {"title": "no id"})

    @patch("app.core.providers.graph.pg_graph_store.async_session_factory")
    @pytest.mark.asyncio
    async def test_create_non_case_node_returns_id(self, mock_factory):
        store = PgGraphStore()
        result = await store.create_node("Statute", {"id": "statute-1"})
        assert result == "statute-1"
        mock_factory.assert_not_called()


class TestPgGraphStoreGetNode:
    """Verify get_node returns case data."""

    @patch("app.core.providers.graph.pg_graph_store.async_session_factory")
    @pytest.mark.asyncio
    async def test_get_existing_node(self, mock_factory):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "case-1", "title": "Test Case", "citation": "2024 SCC 1",
            "court": "SC", "year": 2024, "case_type": "CIVIL",
            "judge": ["Justice A"], "bench_type": "DIVISION", "disposal_nature": "ALLOWED",
        }
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_factory.return_value = mock_session

        store = PgGraphStore()
        node = await store.get_node("case-1")
        assert node is not None
        assert node["title"] == "Test Case"

    @patch("app.core.providers.graph.pg_graph_store.async_session_factory")
    @pytest.mark.asyncio
    async def test_get_nonexistent_node(self, mock_factory):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_factory.return_value = mock_session

        store = PgGraphStore()
        node = await store.get_node("nonexistent")
        assert node is None


class TestPgGraphStoreBatchEdges:
    """Verify batch edge creation."""

    @patch("app.core.providers.graph.pg_graph_store.async_session_factory")
    @pytest.mark.asyncio
    async def test_batch_create_citation_edges(self, mock_factory):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_factory.return_value = mock_session

        store = PgGraphStore()
        edges = [
            {"source_id": "case-1", "target_citation": "2020 SCC 1", "treatment": "FOLLOWED"},
            {"source_id": "case-1", "target_citation": "2019 SCC 2", "treatment": "DISTINGUISHED"},
            {"source_id": "case-1", "target_citation": "2018 SCC 3"},
        ]
        await store.batch_create_citation_edges(edges)
        # execute called twice: once for INSERT, once for UPDATE target_case_id
        assert mock_session.execute.call_count == 2

    @patch("app.core.providers.graph.pg_graph_store.async_session_factory")
    @pytest.mark.asyncio
    async def test_batch_create_empty_edges(self, mock_factory):
        store = PgGraphStore()
        result = await store.batch_create_citation_edges([])
        assert result == 0
        mock_factory.assert_not_called()


class TestPgGraphStoreDeleteNode:
    """Verify delete_node removes citation edges."""

    @patch("app.core.providers.graph.pg_graph_store.async_session_factory")
    @pytest.mark.asyncio
    async def test_delete_node_removes_edges(self, mock_factory):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_factory.return_value = mock_session

        store = PgGraphStore()
        deleted = await store.delete_node("case-1")
        assert deleted is True

    @patch("app.core.providers.graph.pg_graph_store.async_session_factory")
    @pytest.mark.asyncio
    async def test_delete_node_no_edges(self, mock_factory):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_factory.return_value = mock_session

        store = PgGraphStore()
        deleted = await store.delete_node("case-999")
        assert deleted is False


class TestPgGraphStoreGetNeighbors:
    """Verify get_neighbors with direction and depth constraints."""

    @patch("app.core.providers.graph.pg_graph_store.async_session_factory")
    @pytest.mark.asyncio
    async def test_get_neighbors_clamps_depth(self, mock_factory):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_factory.return_value = mock_session

        store = PgGraphStore()
        # Depth 10 should be clamped to 5
        await store.get_neighbors("case-1", depth=10)
        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["max_depth"] == 5

    @pytest.mark.asyncio
    async def test_get_neighbors_validates_relationship(self):
        store = PgGraphStore()
        with pytest.raises(ValueError, match="Invalid relationship"):
            await store.get_neighbors("case-1", relationship="EVIL_REL")


class TestPgGraphStoreEnsureConstraints:
    """Verify ensure_constraints is a no-op for PostgreSQL."""

    @pytest.mark.asyncio
    async def test_ensure_constraints_noop(self):
        store = PgGraphStore()
        # Should not raise
        await store.ensure_constraints()
