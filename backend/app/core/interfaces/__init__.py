"""Protocol interfaces defining contracts for external service providers."""

from app.core.interfaces.document_parser import DocumentParser
from app.core.interfaces.embedder import EmbeddingProvider
from app.core.interfaces.external_doc import ExternalDocProvider
from app.core.interfaces.graph_store import GraphStore
from app.core.interfaces.llm import LLMProvider
from app.core.interfaces.reranker import Reranker, RerankResult
from app.core.interfaces.storage import FileStorage
from app.core.interfaces.translator import TranslationProvider
from app.core.interfaces.tts import TTSProvider
from app.core.interfaces.vector_store import SearchResult, VectorStore
from app.core.interfaces.web_search import WebSearchProvider

__all__ = [
    "DocumentParser",
    "EmbeddingProvider",
    "ExternalDocProvider",
    "FileStorage",
    "GraphStore",
    "LLMProvider",
    "Reranker",
    "RerankResult",
    "SearchResult",
    "TranslationProvider",
    "TTSProvider",
    "VectorStore",
    "WebSearchProvider",
]
