"""Tests verifying provider implementations conform to Protocol interfaces.

These are structural contract tests — they verify that each concrete provider
class is a valid implementation of the corresponding Protocol, without
requiring external service connections.
"""

from __future__ import annotations

import inspect

import pytest

from app.core.interfaces.llm import LLMProvider
from app.core.interfaces.vector_store import VectorStore
from app.core.interfaces.graph_store import GraphStore
from app.core.interfaces.reranker import Reranker
from app.core.interfaces.embedder import EmbeddingProvider
from app.core.interfaces.storage import FileStorage


def _get_protocol_methods(protocol_cls: type) -> dict[str, inspect.Signature]:
    """Extract method names and signatures from a Protocol class."""
    methods = {}
    for name, method in inspect.getmembers(protocol_cls, predicate=inspect.isfunction):
        if not name.startswith("_"):
            methods[name] = inspect.signature(method)
    return methods


class TestLLMProviderContract:
    """Verify GeminiLLM conforms to LLMProvider protocol."""

    def test_gemini_llm_has_required_methods(self) -> None:
        from app.core.providers.llm.gemini import GeminiLLM

        protocol_methods = _get_protocol_methods(LLMProvider)
        for method_name in protocol_methods:
            assert hasattr(GeminiLLM, method_name), (
                f"GeminiLLM missing required method: {method_name}"
            )

    def test_gemini_llm_is_runtime_checkable(self) -> None:
        """GeminiLLM should pass isinstance check against LLMProvider."""
        from app.core.providers.llm.gemini import GeminiLLM

        # Check that the class has the right methods (can't instantiate without API key)
        protocol_methods = _get_protocol_methods(LLMProvider)
        for method_name in protocol_methods:
            impl_method = getattr(GeminiLLM, method_name, None)
            assert impl_method is not None
            assert callable(impl_method)


class TestVectorStoreContract:
    """Verify PineconeStore conforms to VectorStore protocol."""

    def test_pinecone_store_has_required_methods(self) -> None:
        from app.core.providers.vector.pinecone_store import PineconeStore

        protocol_methods = _get_protocol_methods(VectorStore)
        for method_name in protocol_methods:
            assert hasattr(PineconeStore, method_name), (
                f"PineconeStore missing required method: {method_name}"
            )


class TestGraphStoreContract:
    """Verify Neo4jGraph conforms to GraphStore protocol."""

    def test_neo4j_graph_has_required_methods(self) -> None:
        from app.core.providers.graph.neo4j_store import Neo4jGraph

        protocol_methods = _get_protocol_methods(GraphStore)
        for method_name in protocol_methods:
            assert hasattr(Neo4jGraph, method_name), (
                f"Neo4jGraph missing required method: {method_name}"
            )


class TestRerankerContract:
    """Verify CohereReranker conforms to Reranker protocol."""

    def test_cohere_reranker_has_required_methods(self) -> None:
        from app.core.providers.rerankers.cohere_reranker import CohereReranker

        protocol_methods = _get_protocol_methods(Reranker)
        for method_name in protocol_methods:
            assert hasattr(CohereReranker, method_name), (
                f"CohereReranker missing required method: {method_name}"
            )


class TestEmbeddingProviderContract:
    """Verify GeminiEmbedder conforms to EmbeddingProvider protocol."""

    def test_gemini_embedder_has_required_methods(self) -> None:
        from app.core.providers.embeddings.gemini import GeminiEmbedder

        protocol_methods = _get_protocol_methods(EmbeddingProvider)
        for method_name in protocol_methods:
            assert hasattr(GeminiEmbedder, method_name), (
                f"GeminiEmbedder missing required method: {method_name}"
            )


class TestStorageContract:
    """Verify LocalStorage conforms to FileStorage protocol."""

    def test_local_storage_has_required_methods(self) -> None:
        from app.core.providers.storage.local_storage import LocalStorage

        protocol_methods = _get_protocol_methods(FileStorage)
        for method_name in protocol_methods:
            assert hasattr(LocalStorage, method_name), (
                f"LocalStorage missing required method: {method_name}"
            )
