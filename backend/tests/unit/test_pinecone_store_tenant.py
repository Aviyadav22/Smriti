"""Tests for user-scope filtering in PineconeStore.search()."""

from unittest.mock import MagicMock, patch

import pytest


class TestPineconeUserScope:
    """Verify user_scope injects user_id into Pinecone filters."""

    @pytest.fixture()
    def mock_index(self):
        index = MagicMock()
        match = MagicMock()
        match.id = "v1"
        match.score = 0.9
        match.metadata = {"case_id": "c1"}
        index.query.return_value = MagicMock(matches=[match])
        return index

    @patch("app.core.providers.vector.pinecone_store.settings")
    @patch("app.core.providers.vector.pinecone_store.Pinecone")
    @pytest.mark.asyncio
    async def test_search_without_user_scope(self, mock_pc_cls, mock_settings, mock_index):
        mock_settings.pinecone_api_key = "test-key"
        mock_settings.pinecone_host = "https://test"
        mock_pc_cls.return_value.Index.return_value = mock_index

        from app.core.providers.vector.pinecone_store import PineconeStore
        store = PineconeStore()
        await store.search([0.1] * 1536, top_k=5, filters={"court": "SC"})

        call_kwargs = mock_index.query.call_args
        actual_filter = call_kwargs.kwargs.get("filter") or call_kwargs[1].get("filter")
        assert actual_filter == {"court": "SC"}

    @patch("app.core.providers.vector.pinecone_store.settings")
    @patch("app.core.providers.vector.pinecone_store.Pinecone")
    @pytest.mark.asyncio
    async def test_search_with_user_scope(self, mock_pc_cls, mock_settings, mock_index):
        mock_settings.pinecone_api_key = "test-key"
        mock_settings.pinecone_host = "https://test"
        mock_pc_cls.return_value.Index.return_value = mock_index

        from app.core.providers.vector.pinecone_store import PineconeStore
        store = PineconeStore()
        await store.search([0.1] * 1536, top_k=5, user_scope="user-42")

        call_kwargs = mock_index.query.call_args
        filt = call_kwargs.kwargs.get("filter") or call_kwargs[1].get("filter")
        assert filt == {"user_id": "user-42"}

    @patch("app.core.providers.vector.pinecone_store.settings")
    @patch("app.core.providers.vector.pinecone_store.Pinecone")
    @pytest.mark.asyncio
    async def test_search_with_user_scope_merges_filters(self, mock_pc_cls, mock_settings, mock_index):
        mock_settings.pinecone_api_key = "test-key"
        mock_settings.pinecone_host = "https://test"
        mock_pc_cls.return_value.Index.return_value = mock_index

        from app.core.providers.vector.pinecone_store import PineconeStore
        store = PineconeStore()
        await store.search([0.1] * 1536, filters={"court": "SC"}, user_scope="user-42")

        call_kwargs = mock_index.query.call_args
        filt = call_kwargs.kwargs.get("filter") or call_kwargs[1].get("filter")
        assert filt == {"court": "SC", "user_id": "user-42"}
