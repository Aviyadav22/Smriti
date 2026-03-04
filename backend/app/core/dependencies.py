"""FastAPI dependency injection factories for service providers."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.interfaces import (
    DocumentParser,
    EmbeddingProvider,
    FileStorage,
    GraphStore,
    LLMProvider,
    Reranker,
    VectorStore,
)


@lru_cache
def get_llm() -> LLMProvider:
    """Return the configured LLM provider instance."""
    if settings.llm_provider == "gemini":
        from app.core.providers.llm.gemini import GeminiLLM

        return GeminiLLM()
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


@lru_cache
def get_embedder() -> EmbeddingProvider:
    """Return the configured embedding provider instance."""
    if settings.llm_provider == "gemini":
        from app.core.providers.embeddings.gemini import GeminiEmbedder

        return GeminiEmbedder()
    raise ValueError(f"Unknown embedding provider: {settings.llm_provider}")


@lru_cache
def get_vector_store() -> VectorStore:
    """Return the configured vector store instance."""
    if settings.vector_provider == "pinecone":
        from app.core.providers.vector.pinecone_store import PineconeStore

        return PineconeStore()
    raise ValueError(f"Unknown vector provider: {settings.vector_provider}")


@lru_cache
def get_graph_store() -> GraphStore:
    """Return the configured graph store instance."""
    if settings.graph_provider == "neo4j":
        from app.core.providers.graph.neo4j_store import Neo4jGraph

        return Neo4jGraph()
    raise ValueError(f"Unknown graph provider: {settings.graph_provider}")


@lru_cache
def get_reranker() -> Reranker:
    """Return the configured reranker instance."""
    if settings.reranker_provider == "cohere":
        from app.core.providers.rerankers.cohere_reranker import CohereReranker

        return CohereReranker()
    raise ValueError(f"Unknown reranker provider: {settings.reranker_provider}")


@lru_cache
def get_document_parser() -> DocumentParser:
    """Return the configured document parser instance."""
    from app.core.providers.document_parsers.pdf_parser import PDFParser

    return PDFParser()


@lru_cache
def get_storage() -> FileStorage:
    """Return the configured file storage instance."""
    if settings.storage_provider == "local":
        from app.core.providers.storage.local_storage import LocalStorage

        return LocalStorage()
    raise ValueError(f"Unknown storage provider: {settings.storage_provider}")
