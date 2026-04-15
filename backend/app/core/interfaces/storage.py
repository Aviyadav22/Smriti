"""File storage interface for document persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@runtime_checkable
class FileStorage(Protocol):
    """Contract for file storage providers."""

    async def store(self, file_path: str, destination: str) -> str:
        """Store a file and return its storage path."""
        ...

    async def retrieve(self, storage_path: str) -> bytes: ...

    def retrieve_chunked(self, storage_path: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Yield file contents in chunks to avoid loading entire file into memory."""
        ...

    async def delete(self, storage_path: str) -> None: ...

    async def exists(self, storage_path: str) -> bool: ...
