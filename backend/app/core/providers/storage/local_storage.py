"""Local file storage provider implementation."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.core.config import settings


class LocalStorage:
    """Local filesystem storage implementing FileStorage protocol."""

    def __init__(self) -> None:
        self._base_path = Path(settings.local_storage_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    async def store(self, file_path: str, destination: str) -> str:
        dest = self._base_path / destination
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, dest)
        return str(dest)

    async def retrieve(self, storage_path: str) -> bytes:
        return Path(storage_path).read_bytes()

    async def delete(self, storage_path: str) -> None:
        path = Path(storage_path)
        if path.exists():
            path.unlink()

    async def exists(self, storage_path: str) -> bool:
        return Path(storage_path).exists()
