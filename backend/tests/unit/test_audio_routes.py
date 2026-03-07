"""Tests for audio digest API routes."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.api.routes.audio import router


class TestAudioRoutes:
    def test_routes_registered(self) -> None:
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/{case_id}/audio/generate" in paths
        assert "/{case_id}/audio/status" in paths
        assert "/{case_id}/audio" in paths

    def test_generate_is_post(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/{case_id}/audio/generate":
                assert "POST" in route.methods

    def test_status_is_get(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/{case_id}/audio/status":
                assert "GET" in route.methods

    def test_stream_is_get(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/{case_id}/audio":
                assert "GET" in route.methods


class TestRetrieveChunked:
    """Tests for LocalStorage.retrieve_chunked async generator."""

    def test_chunked_yields_multiple_chunks(self, tmp_path: Path) -> None:
        """Verify chunked streaming yields multiple chunks for a file larger than chunk_size."""
        test_file = tmp_path / "test.mp3"
        # Write 20KB of data
        data = b"x" * 20_000
        test_file.write_bytes(data)

        with patch("app.core.providers.storage.local_storage.settings") as mock_settings:
            mock_settings.local_storage_path = str(tmp_path)
            from app.core.providers.storage.local_storage import LocalStorage

            storage = LocalStorage()

        chunks: list[bytes] = []

        async def collect_chunks() -> None:
            async for chunk in storage.retrieve_chunked(str(test_file), chunk_size=8192):
                chunks.append(chunk)

        asyncio.run(collect_chunks())

        # 20000 / 8192 = 2.44, so we expect 3 chunks
        assert len(chunks) == 3
        assert b"".join(chunks) == data

    def test_chunked_file_not_found(self, tmp_path: Path) -> None:
        """Verify FileNotFoundError for missing files."""
        with patch("app.core.providers.storage.local_storage.settings") as mock_settings:
            mock_settings.local_storage_path = str(tmp_path)
            from app.core.providers.storage.local_storage import LocalStorage

            storage = LocalStorage()

        async def attempt_read() -> None:
            async for _ in storage.retrieve_chunked(str(tmp_path / "nonexistent.mp3")):
                pass

        with pytest.raises(FileNotFoundError):
            asyncio.run(attempt_read())

    def test_chunked_small_file_single_chunk(self, tmp_path: Path) -> None:
        """A file smaller than chunk_size should yield exactly one chunk."""
        test_file = tmp_path / "small.mp3"
        data = b"small audio"
        test_file.write_bytes(data)

        with patch("app.core.providers.storage.local_storage.settings") as mock_settings:
            mock_settings.local_storage_path = str(tmp_path)
            from app.core.providers.storage.local_storage import LocalStorage

            storage = LocalStorage()

        chunks: list[bytes] = []

        async def collect_chunks() -> None:
            async for chunk in storage.retrieve_chunked(str(test_file), chunk_size=8192):
                chunks.append(chunk)

        asyncio.run(collect_chunks())

        assert len(chunks) == 1
        assert chunks[0] == data
