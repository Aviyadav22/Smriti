"""File storage interface for document persistence."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class FileStorage(Protocol):
    """Contract for file storage providers."""

    async def store(self, file_path: str, destination: str) -> str:
        """Store a file and return its storage path."""
        ...

    async def retrieve(self, storage_path: str) -> bytes: ...

    async def delete(self, storage_path: str) -> None: ...

    async def exists(self, storage_path: str) -> bool: ...
