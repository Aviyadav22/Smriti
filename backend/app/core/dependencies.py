"""FastAPI dependency injection factories for service providers."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.interfaces import (
    EmbeddingProvider,
    ExternalDocProvider,
    FileStorage,
    GraphStore,
    LLMProvider,
    Reranker,
    TTSProvider,
    TranslationProvider,
    VectorStore,
    WebSearchProvider,
)


@lru_cache
def get_llm() -> LLMProvider:
    """Return the configured LLM provider instance."""
    if settings.llm_provider == "gemini":
        from app.core.providers.llm.gemini import GeminiLLM

        return GeminiLLM()
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


@lru_cache
def get_flash_llm() -> LLMProvider:
    """Return the configured fast/cheap LLM provider instance (Gemini Flash)."""
    if settings.llm_provider == "gemini":
        from app.core.providers.llm.gemini import GeminiLLM

        return GeminiLLM(model=settings.gemini_flash_model)
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
    if settings.vector_provider == "pgvector":
        from app.core.providers.vector.pgvector_store import PgvectorStore

        return PgvectorStore()
    raise ValueError(f"Unknown vector provider: {settings.vector_provider}")


@lru_cache
def get_graph_store() -> GraphStore:
    """Return the configured graph store instance."""
    if settings.graph_provider == "neo4j":
        from app.core.providers.graph.neo4j_store import Neo4jGraph

        return Neo4jGraph()
    if settings.graph_provider == "postgresql":
        from app.core.providers.graph.pg_graph_store import PgGraphStore

        return PgGraphStore()
    raise ValueError(f"Unknown graph provider: {settings.graph_provider}")


@lru_cache
def get_reranker() -> Reranker:
    """Return the configured reranker instance."""
    if settings.reranker_provider == "cohere":
        from app.core.providers.rerankers.cohere_reranker import CohereReranker

        return CohereReranker()
    raise ValueError(f"Unknown reranker provider: {settings.reranker_provider}")


@lru_cache
def get_translator() -> TranslationProvider:
    """Return the configured translation provider instance."""
    if settings.llm_provider == "gemini":
        from app.core.providers.translation.gemini_translator import GeminiTranslator

        return GeminiTranslator()
    raise ValueError(f"Unknown translation provider for: {settings.llm_provider}")


@lru_cache
def get_storage() -> FileStorage:
    """Return the configured file storage instance."""
    if settings.storage_provider == "local":
        from app.core.providers.storage.local_storage import LocalStorage

        return LocalStorage()
    if settings.storage_provider == "gcs":
        from app.core.providers.storage.gcs_storage import GCSStorage

        return GCSStorage()
    raise ValueError(f"Unknown storage provider: {settings.storage_provider}")


@lru_cache
def get_tts() -> TTSProvider:
    """Return the configured TTS provider instance."""
    if settings.tts_provider == "sarvam" and settings.sarvam_api_key:
        from app.core.providers.tts.sarvam import SarvamTTS

        return SarvamTTS()
    from app.core.providers.tts.mock_tts import MockTTS

    return MockTTS()


@lru_cache
def get_checkpointer() -> object:
    """Return the appropriate LangGraph checkpointer for the current environment.

    In production/staging, uses AsyncPostgresSaver backed by the main PostgreSQL
    database. In development/testing, uses an in-memory MemorySaver.
    """
    if settings.app_env in ("production", "staging"):
        from app.core.agents.checkpointer import get_checkpointer_connection_string
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        return AsyncPostgresSaver.from_conn_string(get_checkpointer_connection_string())
    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()


@lru_cache
def get_web_search() -> WebSearchProvider:
    """Return the configured web search provider instance."""
    from app.core.providers.web_search.tavily import TavilySearchClient

    return TavilySearchClient()


@lru_cache
def get_ik_client() -> ExternalDocProvider:
    """Return the configured Indian Kanoon API client instance."""
    from app.core.providers.external.indiankanoon import IndianKanoonClient

    return IndianKanoonClient()


async def cleanup_providers() -> None:
    """Close cached provider connections on shutdown and clear LRU caches."""
    try:
        if get_graph_store.cache_info().currsize > 0:
            store = get_graph_store()
            if hasattr(store, "close"):
                await store.close()
            get_graph_store.cache_clear()
    except Exception:
        pass
    try:
        if get_reranker.cache_info().currsize > 0:
            reranker = get_reranker()
            if hasattr(reranker, "close"):
                await reranker.close()
            get_reranker.cache_clear()
    except Exception:
        pass
    try:
        if get_ik_client.cache_info().currsize > 0:
            ik = get_ik_client()
            if hasattr(ik, "close"):
                await ik.close()
            get_ik_client.cache_clear()
    except Exception:
        pass
    try:
        if get_web_search.cache_info().currsize > 0:
            ws = get_web_search()
            if hasattr(ws, "close"):
                await ws.close()
            get_web_search.cache_clear()
    except Exception:
        pass
