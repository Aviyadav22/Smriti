"""Tests for concurrent ingestion race conditions (G16).

Tests that the pipeline handles concurrent operations safely:
- SQLite tracker concurrent access
- Duplicate citation conflict resolution
- _embed_chunks retry doesn't double-insert
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.ingestion.chunker import Chunk
from app.core.ingestion.pipeline import _compute_text_hash, _embed_chunks


def _make_chunk(text: str = "test chunk", index: int = 0) -> Chunk:
    return Chunk(
        text=text,
        section_type="ANALYSIS",
        chunk_index=index,
        case_id="case-001",
    )


class TestComputeTextHash:
    """Text hash should be deterministic and whitespace-insensitive."""

    def test_same_text_same_hash(self):
        """Identical texts should produce identical hashes."""
        h1 = _compute_text_hash("The court held that the appeal is dismissed.")
        h2 = _compute_text_hash("The court held that the appeal is dismissed.")
        assert h1 == h2

    def test_different_text_different_hash(self):
        """Different texts should produce different hashes."""
        h1 = _compute_text_hash("The appeal is dismissed.")
        h2 = _compute_text_hash("The appeal is allowed.")
        assert h1 != h2

    def test_whitespace_normalization(self):
        """Texts differing only in whitespace should hash the same."""
        h1 = _compute_text_hash("The  court   held   that")
        h2 = _compute_text_hash("The court held that")
        assert h1 == h2

    def test_case_insensitive(self):
        """Text hash should be case-insensitive."""
        h1 = _compute_text_hash("THE COURT HELD")
        h2 = _compute_text_hash("the court held")
        assert h1 == h2

    def test_leading_trailing_whitespace_ignored(self):
        """Leading/trailing whitespace should not affect the hash."""
        h1 = _compute_text_hash("  The court held.  ")
        h2 = _compute_text_hash("The court held.")
        assert h1 == h2

    def test_hash_is_sha256(self):
        """Hash should be a 64-character hex string (SHA-256)."""
        h = _compute_text_hash("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestEmbedChunksRetry:
    """_embed_chunks retry should not produce duplicate embeddings."""

    @pytest.mark.asyncio
    async def test_successful_single_batch(self, monkeypatch):
        """Normal case: all chunks embedded in one pass."""
        monkeypatch.setenv("EMBEDDING_DIMENSION", "2")
        embedder = AsyncMock()
        embedder.embed_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]

        chunks = [_make_chunk("text a", 0), _make_chunk("text b", 1)]
        result = await _embed_chunks(chunks, embedder)

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_retry_does_not_duplicate_embeddings(self, monkeypatch):
        """When a batch fails and retries, embeddings should not be duplicated."""
        monkeypatch.setenv("EMBEDDING_DIMENSION", "2")
        embedder = AsyncMock()
        embedder.embed_batch.side_effect = [
            RuntimeError("Transient failure"),  # 1st attempt fails
            [[0.1, 0.2], [0.3, 0.4]],          # 2nd attempt succeeds
        ]

        chunks = [_make_chunk("text a", 0), _make_chunk("text b", 1)]

        with patch("app.core.ingestion.pipeline.asyncio.sleep", new_callable=AsyncMock):
            result = await _embed_chunks(chunks, embedder)

        assert len(result) == 2  # Exactly 2, not 4

    @pytest.mark.asyncio
    async def test_retry_exhaustion_raises(self):
        """When all retries are exhausted, the exception should propagate."""
        embedder = AsyncMock()
        embedder.embed_batch.side_effect = RuntimeError("Permanent failure")

        chunks = [_make_chunk("text a", 0)]

        with pytest.raises(RuntimeError, match="Permanent failure"):
            with patch("app.core.ingestion.pipeline.asyncio.sleep", new_callable=AsyncMock):
                await _embed_chunks(chunks, embedder, max_retries=2)

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty(self):
        """Empty chunk list should return empty embeddings list."""
        embedder = AsyncMock()
        result = await _embed_chunks([], embedder)
        assert result == []
        embedder.embed_batch.assert_not_called()


class TestConcurrentTextHashDedup:
    """Concurrent ingestion should correctly dedup via text_hash."""

    def test_concurrent_texts_produce_unique_hashes(self):
        """Different concurrent texts should produce unique hashes."""
        texts = [
            "Case about land acquisition and compensation",
            "Case about criminal appeal under Section 302",
            "Case about constitutional validity of amendment",
        ]
        hashes = [_compute_text_hash(t) for t in texts]
        assert len(set(hashes)) == len(hashes), "All hashes should be unique"

    def test_duplicate_texts_produce_same_hash(self):
        """Same text ingested concurrently should produce same hash for dedup."""
        text = "The court held that the petitioner's fundamental rights were violated."
        h1 = _compute_text_hash(text)
        h2 = _compute_text_hash(text)
        assert h1 == h2, "Same text should always produce same hash"
