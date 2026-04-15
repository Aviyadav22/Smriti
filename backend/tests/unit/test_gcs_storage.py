"""Tests for Google Cloud Storage provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.interfaces.storage import FileStorage


@pytest.fixture
def mock_gcs_client():
    """Patch google.cloud.storage.Client and return mock bucket/blob."""
    with (
        patch("app.core.providers.storage.gcs_storage.storage") as mock_storage,
        patch("app.core.providers.storage.gcs_storage.settings") as mock_settings,
    ):
        mock_settings.gcs_bucket_name = "test-bucket"

        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_client.bucket.return_value = mock_bucket
        mock_storage.Client.return_value = mock_client

        from app.core.providers.storage.gcs_storage import GCSStorage

        store = GCSStorage()

        yield store, mock_bucket


class TestGCSStorageStore:
    @pytest.mark.asyncio
    async def test_store_uploads_file(self, mock_gcs_client: tuple) -> None:
        store, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        with patch("os.path.getsize", return_value=1024):
            result = await store.store("/tmp/test.pdf", "cases/test.pdf")

        mock_bucket.blob.assert_called_once_with("cases/test.pdf")
        mock_blob.upload_from_filename.assert_called_once_with("/tmp/test.pdf")
        assert result == "gs://test-bucket/cases/test.pdf"

    @pytest.mark.asyncio
    async def test_store_rejects_oversized_file(self, mock_gcs_client: tuple) -> None:
        store, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        with patch("os.path.getsize", return_value=600 * 1024 * 1024):
            with pytest.raises(ValueError, match="exceeds maximum"):
                await store.store("/tmp/huge.pdf", "cases/huge.pdf")


class TestGCSStorageRetrieve:
    @pytest.mark.asyncio
    async def test_retrieve_downloads_bytes(self, mock_gcs_client: tuple) -> None:
        store, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"file-content"
        mock_bucket.blob.return_value = mock_blob

        result = await store.retrieve("gs://test-bucket/cases/test.pdf")

        mock_bucket.blob.assert_called_once_with("cases/test.pdf")
        mock_blob.download_as_bytes.assert_called_once()
        assert result == b"file-content"


class TestGCSStorageRetrieveChunked:
    @pytest.mark.asyncio
    async def test_retrieve_chunked_yields_chunks(self, mock_gcs_client: tuple) -> None:
        store, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        # 10 bytes of data, chunk_size=4 => 3 chunks (4+4+2)
        mock_blob.download_as_bytes.return_value = b"0123456789"
        mock_bucket.blob.return_value = mock_blob

        chunks: list[bytes] = []
        async for chunk in store.retrieve_chunked("gs://test-bucket/doc.pdf", chunk_size=4):
            chunks.append(chunk)

        assert chunks == [b"0123", b"4567", b"89"]
        mock_bucket.blob.assert_called_once_with("doc.pdf")


class TestGCSStorageDelete:
    @pytest.mark.asyncio
    async def test_delete_removes_blob(self, mock_gcs_client: tuple) -> None:
        store, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        await store.delete("gs://test-bucket/cases/test.pdf")

        mock_blob.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_handles_not_found(self, mock_gcs_client: tuple) -> None:
        from google.api_core.exceptions import NotFound

        store, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_blob.delete.side_effect = NotFound("blob not found")
        mock_bucket.blob.return_value = mock_blob

        # Should not raise
        await store.delete("gs://test-bucket/missing.pdf")


class TestGCSStorageExists:
    @pytest.mark.asyncio
    async def test_exists_returns_true_when_blob_exists(self, mock_gcs_client: tuple) -> None:
        store, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob

        assert await store.exists("gs://test-bucket/cases/test.pdf") is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_when_blob_missing(self, mock_gcs_client: tuple) -> None:
        store, mock_bucket = mock_gcs_client
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        mock_bucket.blob.return_value = mock_blob

        assert await store.exists("gs://test-bucket/missing.pdf") is False


class TestGCSStorageParseGsPath:
    def test_parse_gs_path_extracts_blob_name(self, mock_gcs_client: tuple) -> None:
        store, _ = mock_gcs_client
        assert store._parse_gs_path("gs://test-bucket/cases/test.pdf") == "cases/test.pdf"

    def test_parse_gs_path_handles_plain_path(self, mock_gcs_client: tuple) -> None:
        store, _ = mock_gcs_client
        assert store._parse_gs_path("cases/test.pdf") == "cases/test.pdf"


class TestGCSStorageProtocol:
    def test_protocol_compliance(self, mock_gcs_client: tuple) -> None:
        store, _ = mock_gcs_client
        assert isinstance(store, FileStorage)
