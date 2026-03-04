"""Embedding provider interface for text vectorization."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Contract for text embedding providers."""

    async def embed_text(self, text: str) -> list[float]: ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimension(self) -> int: ...
