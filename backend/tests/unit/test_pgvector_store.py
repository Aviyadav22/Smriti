"""Tests for PgvectorStore — pgvector-based vector store provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.interfaces.vector_store import SearchResult
from app.core.providers.vector.pgvector_store import PgvectorStore, _build_filter_clause

# ---------------------------------------------------------------------------
# Filter translation tests
# ---------------------------------------------------------------------------


class TestBuildFilterClause:
    """Verify Pinecone-style filter dicts translate to correct SQL."""

    def test_eq_filter(self):
        params: dict = {}
        clause = _build_filter_clause({"court": {"$eq": "SC"}}, params)
        assert "metadata->>'court' = :f_0" in clause
        assert params["f_0"] == "SC"

    def test_gte_lte_filter(self):
        params: dict = {}
        clause = _build_filter_clause({"year": {"$gte": 2020, "$lte": 2025}}, params)
        assert "(metadata->>'year')::int >= :f_0" in clause
        assert "(metadata->>'year')::int <= :f_1" in clause
        assert params["f_0"] == 2020
        assert params["f_1"] == 2025

    def test_in_filter_single_element(self):
        params: dict = {}
        clause = _build_filter_clause({"acts_cited": {"$in": ["IPC"]}}, params)
        assert "metadata->'acts_cited' ? :f_0" in clause
        assert params["f_0"] == "IPC"

    def test_in_filter_multiple_elements(self):
        params: dict = {}
        clause = _build_filter_clause({"court": {"$in": ["SC", "HC"]}}, params)
        assert "metadata->>'court' IN (:f_0_0, :f_0_1)" in clause
        assert params["f_0_0"] == "SC"
        assert params["f_0_1"] == "HC"

    def test_bare_value_filter(self):
        params: dict = {}
        clause = _build_filter_clause({"user_id": "user-42"}, params)
        assert "metadata->>'user_id' = :f_0" in clause
        assert params["f_0"] == "user-42"

    def test_ne_filter(self):
        params: dict = {}
        clause = _build_filter_clause({"court": {"$ne": "HC"}}, params)
        assert "metadata->>'court' != :f_0" in clause
        assert params["f_0"] == "HC"

    def test_empty_filters(self):
        params: dict = {}
        clause = _build_filter_clause({}, params)
        assert clause == "TRUE"

    def test_combined_filters(self):
        params: dict = {}
        clause = _build_filter_clause({"court": {"$eq": "SC"}, "year": {"$gte": 2020}}, params)
        assert " AND " in clause
        assert len(params) == 2


# ---------------------------------------------------------------------------
# PgvectorStore unit tests (mocked DB)
# ---------------------------------------------------------------------------


class TestPgvectorStoreSearch:
    """Verify search translates to correct SQL and returns SearchResult objects."""

    @pytest.fixture()
    def mock_session(self):
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        return session

    @patch("app.core.providers.vector.pgvector_store.async_session_factory")
    @patch("app.core.providers.vector.pgvector_store.settings")
    @pytest.mark.asyncio
    async def test_search_returns_results(self, mock_settings, mock_factory):
        mock_settings.gemini_embedding_dimension = 1536

        # Mock DB response
        row = MagicMock()
        row.id = "case1_0"
        row.score = 0.95
        row.metadata = {"case_id": "case1", "text": "some text"}

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [row]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_factory.return_value = mock_session

        store = PgvectorStore()
        results = await store.search([0.1] * 1536, top_k=5)

        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].id == "case1_0"
        assert results[0].score == 0.95
        assert results[0].metadata["case_id"] == "case1"

    @patch("app.core.providers.vector.pgvector_store.async_session_factory")
    @patch("app.core.providers.vector.pgvector_store.settings")
    @pytest.mark.asyncio
    async def test_search_with_user_scope(self, mock_settings, mock_factory):
        mock_settings.gemini_embedding_dimension = 1536

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_factory.return_value = mock_session

        store = PgvectorStore()
        await store.search([0.1] * 1536, top_k=5, user_scope="user-42")

        # Verify the SQL includes user_id filter
        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "user_id" in str(call_args[0][1]) or "user_id" in sql_text

    @patch("app.core.providers.vector.pgvector_store.async_session_factory")
    @patch("app.core.providers.vector.pgvector_store.settings")
    @pytest.mark.asyncio
    async def test_search_returns_empty_on_error(self, mock_settings, mock_factory):
        mock_settings.gemini_embedding_dimension = 1536

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(side_effect=Exception("DB error"))
        mock_factory.return_value = mock_session

        store = PgvectorStore()
        results = await store.search([0.1] * 1536, top_k=5)
        assert results == []


class TestPgvectorStoreUpsert:
    """Verify upsert constructs correct SQL."""

    @patch("app.core.providers.vector.pgvector_store.async_session_factory")
    @patch("app.core.providers.vector.pgvector_store.settings")
    @pytest.mark.asyncio
    async def test_upsert_empty_vectors(self, mock_settings, mock_factory):
        mock_settings.gemini_embedding_dimension = 1536
        store = PgvectorStore()
        await store.upsert([])
        mock_factory.assert_not_called()

    @patch("app.core.providers.vector.pgvector_store.async_session_factory")
    @patch("app.core.providers.vector.pgvector_store.settings")
    @pytest.mark.asyncio
    async def test_upsert_calls_execute(self, mock_settings, mock_factory):
        mock_settings.gemini_embedding_dimension = 1536

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_factory.return_value = mock_session

        store = PgvectorStore()
        await store.upsert(
            [
                {
                    "id": "case1_0",
                    "values": [0.1] * 1536,
                    "metadata": {"case_id": "case1", "chunk_index": 0, "text": "hello"},
                }
            ]
        )

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


class TestPgvectorStoreDelete:
    """Verify delete operations."""

    @patch("app.core.providers.vector.pgvector_store.async_session_factory")
    @patch("app.core.providers.vector.pgvector_store.settings")
    @pytest.mark.asyncio
    async def test_delete_by_metadata_without_exclude(self, mock_settings, mock_factory):
        mock_settings.gemini_embedding_dimension = 1536

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_factory.return_value = mock_session

        store = PgvectorStore()
        await store.delete_by_metadata({"case_id": "case1"})

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch("app.core.providers.vector.pgvector_store.async_session_factory")
    @patch("app.core.providers.vector.pgvector_store.settings")
    @pytest.mark.asyncio
    async def test_delete_by_metadata_with_exclude(self, mock_settings, mock_factory):
        mock_settings.gemini_embedding_dimension = 1536

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_factory.return_value = mock_session

        store = PgvectorStore()
        await store.delete_by_metadata(
            {"case_id": "case1"},
            exclude_ids=["case1_0", "case1_1"],
        )

        # Verify SQL includes NOT IN clause
        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "NOT IN" in sql_text
