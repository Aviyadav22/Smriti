"""Tests for Pinecone metadata text truncation and warning logging."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest

from app.core.ingestion.chunker import Chunk
from app.core.ingestion.metadata import CaseMetadata
from app.core.ingestion.pipeline import _upsert_vectors


def _make_chunk(text: str, chunk_index: int = 0, case_id: str = "test_case") -> Chunk:
    return Chunk(
        text=text,
        section_type="ANALYSIS",
        chunk_index=chunk_index,
        case_id=case_id,
    )


def _make_metadata() -> CaseMetadata:
    return CaseMetadata(
        title="Test Case",
        court="Supreme Court of India",
        year=2024,
        judge=["Justice A"],
    )


@pytest.mark.asyncio
async def test_truncation_warning_logged_when_chunk_exceeds_2000(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A WARNING log should be emitted when chunk text exceeds 2000 chars."""
    long_text = "x" * 2500
    chunk = _make_chunk(long_text)
    embedding = [0.1] * 10
    vector_store = AsyncMock()

    with caplog.at_level(logging.WARNING, logger="app.core.ingestion.pipeline"):
        await _upsert_vectors("test_case", [chunk], [embedding], _make_metadata(), vector_store)

    assert any(
        "truncated" in record.message for record in caplog.records
    ), f"Expected a 'truncated' warning, got: {[r.message for r in caplog.records]}"


@pytest.mark.asyncio
async def test_upserted_text_capped_at_2000() -> None:
    """The text field in Pinecone metadata must be at most 2000 chars."""
    long_text = "a" * 2500
    chunk = _make_chunk(long_text)
    embedding = [0.1] * 10
    vector_store = AsyncMock()

    await _upsert_vectors("test_case", [chunk], [embedding], _make_metadata(), vector_store)

    # vector_store.upsert is called with a list of vector dicts
    call_args = vector_store.upsert.call_args[0][0]
    upserted_text = call_args[0]["metadata"]["text"]
    assert len(upserted_text) == 2000


@pytest.mark.asyncio
async def test_no_warning_when_chunk_within_limit(caplog: pytest.LogCaptureFixture) -> None:
    """No truncation warning when text is within 2000 chars."""
    short_text = "y" * 1500
    chunk = _make_chunk(short_text)
    embedding = [0.1] * 10
    vector_store = AsyncMock()

    with caplog.at_level(logging.WARNING, logger="app.core.ingestion.pipeline"):
        await _upsert_vectors("test_case", [chunk], [embedding], _make_metadata(), vector_store)

    assert not any("truncated" in record.message for record in caplog.records)
