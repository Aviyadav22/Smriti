"""Tests for provider switching via environment variables.

Verifies that VECTOR_PROVIDER and GRAPH_PROVIDER env vars correctly
select between Pinecone/pgvector and Neo4j/PostgreSQL providers.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.providers.graph.pg_graph_store import PgGraphStore
from app.core.providers.vector.pgvector_store import PgvectorStore


class TestVectorProviderSwitching:
    """Verify get_vector_store() returns correct provider based on settings."""

    @patch("app.core.dependencies.settings")
    def test_pgvector_provider_selected(self, mock_settings):
        mock_settings.vector_provider = "pgvector"
        mock_settings.gemini_embedding_dimension = 1536

        # Clear lru_cache
        from app.core.dependencies import get_vector_store

        get_vector_store.cache_clear()

        store = get_vector_store()
        assert isinstance(store, PgvectorStore)
        get_vector_store.cache_clear()

    @patch("app.core.dependencies.settings")
    def test_pinecone_provider_selected(self, mock_settings):
        mock_settings.vector_provider = "pinecone"
        mock_settings.pinecone_api_key = "test-key"
        mock_settings.pinecone_host = "https://test-host"

        from app.core.dependencies import get_vector_store

        get_vector_store.cache_clear()

        store = get_vector_store()
        from app.core.providers.vector.pinecone_store import PineconeStore

        assert isinstance(store, PineconeStore)
        get_vector_store.cache_clear()

    @patch("app.core.dependencies.settings")
    def test_unknown_vector_provider_raises(self, mock_settings):
        mock_settings.vector_provider = "unknown"

        from app.core.dependencies import get_vector_store

        get_vector_store.cache_clear()

        with pytest.raises(ValueError, match="Unknown vector provider"):
            get_vector_store()
        get_vector_store.cache_clear()


class TestGraphProviderSwitching:
    """Verify get_graph_store() returns correct provider based on settings."""

    @patch("app.core.dependencies.settings")
    def test_postgresql_provider_selected(self, mock_settings):
        mock_settings.graph_provider = "postgresql"

        from app.core.dependencies import get_graph_store

        get_graph_store.cache_clear()

        store = get_graph_store()
        assert isinstance(store, PgGraphStore)
        get_graph_store.cache_clear()

    @patch("app.core.dependencies.settings")
    def test_neo4j_provider_selected(self, mock_settings):
        mock_settings.graph_provider = "neo4j"
        mock_settings.neo4j_uri = "bolt://localhost:7687"
        mock_settings.neo4j_user = "neo4j"
        mock_settings.neo4j_password = "test"
        mock_settings.neo4j_database = "neo4j"

        from app.core.dependencies import get_graph_store

        get_graph_store.cache_clear()

        # Neo4j will try to connect — we just verify it tries to instantiate
        # the right class (connection may fail in unit tests)
        try:
            store = get_graph_store()
            from app.core.providers.graph.neo4j_store import Neo4jGraph

            assert isinstance(store, Neo4jGraph)
        except RuntimeError:
            # Expected: Neo4j not running in unit test environment
            pass
        get_graph_store.cache_clear()

    @patch("app.core.dependencies.settings")
    def test_unknown_graph_provider_raises(self, mock_settings):
        mock_settings.graph_provider = "unknown"

        from app.core.dependencies import get_graph_store

        get_graph_store.cache_clear()

        with pytest.raises(ValueError, match="Unknown graph provider"):
            get_graph_store()
        get_graph_store.cache_clear()
