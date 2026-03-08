"""Google Cloud Storage provider implementation."""

from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import AsyncIterator

from google.api_core.exceptions import NotFound
from google.cloud import storage

from app.core.config import settings

logger = logging.getLogger(__name__)


class GCSStorage:
    """Google Cloud Storage implementing FileStorage protocol.

    Authentication is handled via Workload Identity on Cloud Run
    (default credentials — no API key needed).
    """

    def __init__(self) -> None:
        self._client = storage.Client()
        self._bucket = self._client.bucket(settings.gcs_bucket_name)

    def _parse_gs_path(self, storage_path: str) -> str:
        """Extract blob name from gs://bucket/path or plain path."""
        prefix = f"gs://{self._bucket.name}/"
        if storage_path.startswith(prefix):
            return storage_path[len(prefix):]
        if storage_path.startswith("gs://"):
            # gs://other-bucket/path — strip gs://bucket/ portion
            parts = storage_path[len("gs://"):]
            _, _, blob_name = parts.partition("/")
            return blob_name
        return storage_path

    # Maximum upload size: 500 MB
    MAX_UPLOAD_BYTES = 500 * 1024 * 1024

    async def store(self, file_path: str, destination: str) -> str:
        """Upload a file to GCS and return its gs:// path."""
        import os

        file_size = await asyncio.to_thread(os.path.getsize, file_path)
        if file_size > self.MAX_UPLOAD_BYTES:
            raise ValueError(
                f"File size {file_size} bytes exceeds maximum "
                f"upload limit of {self.MAX_UPLOAD_BYTES} bytes"
            )
        blob = self._bucket.blob(destination)
        await asyncio.to_thread(blob.upload_from_filename, file_path)
        gs_path = f"gs://{self._bucket.name}/{destination}"
        logger.info("Stored file to GCS: %s", gs_path)
        return gs_path

    async def retrieve(self, storage_path: str) -> bytes:
        """Download a file from GCS as bytes."""
        blob_name = self._parse_gs_path(storage_path)
        blob = self._bucket.blob(blob_name)
        return await asyncio.to_thread(blob.download_as_bytes)

    async def retrieve_chunked(
        self, storage_path: str, chunk_size: int = 8192
    ) -> AsyncIterator[bytes]:
        """Yield file contents in chunks to avoid loading entire file into memory."""
        blob_name = self._parse_gs_path(storage_path)
        blob = self._bucket.blob(blob_name)

        # Download into a BytesIO buffer in a thread, then yield chunks
        raw = await asyncio.to_thread(blob.download_as_bytes)
        buffer = io.BytesIO(raw)
        while True:
            chunk = buffer.read(chunk_size)
            if not chunk:
                break
            yield chunk

    async def delete(self, storage_path: str) -> None:
        """Delete a blob from GCS. Silently ignores missing blobs."""
        blob_name = self._parse_gs_path(storage_path)
        blob = self._bucket.blob(blob_name)
        try:
            await asyncio.to_thread(blob.delete)
            logger.info("Deleted GCS blob: %s", blob_name)
        except NotFound:
            logger.debug("Blob not found (already deleted): %s", blob_name)

    async def exists(self, storage_path: str) -> bool:
        """Check if a blob exists in GCS."""
        blob_name = self._parse_gs_path(storage_path)
        blob = self._bucket.blob(blob_name)
        return await asyncio.to_thread(blob.exists)
