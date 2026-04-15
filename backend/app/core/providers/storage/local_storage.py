"""Local file storage provider implementation."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class LocalStorage:
    """Local filesystem storage implementing FileStorage protocol."""

    def __init__(self) -> None:
        self._base_path = Path(settings.local_storage_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, destination: str) -> Path:
        """Resolve destination and verify it stays within the base storage directory.

        Raises:
            ValueError: If the resolved path escapes the base directory
                (path traversal attempt).
        """
        base_resolved = self._base_path.resolve()
        full_path = (base_resolved / destination).resolve()
        # Ensure the resolved path is within the base directory.
        # Append os.sep to avoid prefix false-positives (e.g. /storage-evil matching /storage).
        if not (
            full_path == base_resolved or str(full_path).startswith(str(base_resolved) + os.sep)
        ):
            raise ValueError(
                f"Path traversal detected: '{destination}' resolves outside "
                f"the storage directory"
            )
        return full_path

    async def store(self, file_path: str, destination: str) -> str:
        dest = self._safe_path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, dest)
        return str(dest)

    async def retrieve(self, storage_path: str) -> bytes:
        safe = self._safe_path(storage_path)
        return safe.read_bytes()

    async def retrieve_chunked(
        self, storage_path: str, chunk_size: int = 8192
    ) -> AsyncIterator[bytes]:
        """Yield file contents in chunks to avoid loading entire file into memory."""
        full_path = self._safe_path(storage_path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {storage_path}")
        with open(full_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    async def delete(self, storage_path: str) -> None:
        path = self._safe_path(storage_path)
        if path.exists():
            path.unlink()

    async def exists(self, storage_path: str) -> bool:
        safe = self._safe_path(storage_path)
        return safe.exists()
