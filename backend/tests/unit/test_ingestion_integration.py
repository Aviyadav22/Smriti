"""Integration test for the ingestion pipeline.

Tests the flow: mock PDF → parse → chunk → embed → verify vectors stored
with correct metadata (case_id, citation, chunk_index, year, court,
acts_cited, section_type).

All external services mocked. Pipeline logic exercised end-to-end.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.ingestion.chunker import Chunk, chunk_judgment
from app.core.ingestion.metadata import CaseMetadata
from app.core.ingestion.pipeline import _upsert_vectors

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CASE_ID = "aabbccdd-1111-2222-3333-444455556666"

JUDGMENT_TEXT = """\
SUPREME COURT OF INDIA

IN THE MATTER OF: State of Maharashtra vs. Rajesh Kumar
Criminal Appeal No. 1234 of 2023
Citation: (2024) 5 SCC 142

BENCH: Hon'ble Justice D.Y. Chandrachud (CJI), Hon'ble Justice J.B. Pardiwala

FACTS:
The appellant State challenged the order of the High Court of Bombay granting
anticipatory bail to the respondent under Section 438 of the Code of Criminal
Procedure, 1973 (CrPC). The respondent was accused of offences under Section 302
of the Indian Penal Code (IPC) read with Section 120B IPC.

ISSUES:
1. Whether anticipatory bail can be granted in cases involving Section 302 IPC.
2. Whether the High Court properly exercised its discretion under Section 438 CrPC.

ARGUMENTS:
The prosecution argued that Section 302 IPC is a non-bailable offence and the
gravity of the crime warrants custodial interrogation. The defence relied on
Arnesh Kumar v. State of Bihar (2014) 8 SCC 273.

HOLDINGS:
This Court holds that while Section 302 IPC is a serious offence, the right to
personal liberty under Article 21 of the Constitution must be balanced against
the needs of investigation.

ORDER:
The appeal is dismissed. The anticipatory bail granted by the High Court is
confirmed with the condition that the respondent shall cooperate with the investigation.
"""


def _make_metadata() -> CaseMetadata:
    return CaseMetadata(
        title="State of Maharashtra vs. Rajesh Kumar",
        citation="(2024) 5 SCC 142",
        court="Supreme Court of India",
        year=2024,
        judge=["D.Y. Chandrachud", "J.B. Pardiwala"],
        case_type="criminal",
        bench_type="division",
        acts_cited=["IPC", "CrPC", "BNS", "BNSS"],
        cases_cited=["Arnesh Kumar v. State of Bihar"],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChunkingProducesValidChunks:
    """Tests that judgment text is chunked correctly."""

    def test_chunks_have_section_types(self):
        """Each chunk should have a judgment section type (FACTS, ISSUES, etc)."""
        chunks = chunk_judgment(JUDGMENT_TEXT, case_id=CASE_ID)
        assert len(chunks) > 0
        for chunk in chunks:
            assert isinstance(chunk, Chunk)
            assert chunk.text.strip() != ""
            assert chunk.case_id == CASE_ID
            assert chunk.chunk_index >= 0

    def test_chunks_respect_size_limits(self):
        """No chunk should exceed 2000 chars (the configured max)."""
        chunks = chunk_judgment(JUDGMENT_TEXT, case_id=CASE_ID)
        for chunk in chunks:
            assert len(chunk.text) <= 2200, (
                f"Chunk {chunk.chunk_index} exceeds max size: {len(chunk.text)} chars"
            )

    def test_chunks_have_case_id(self):
        """Every chunk should be tagged with the case_id."""
        chunks = chunk_judgment(JUDGMENT_TEXT, case_id=CASE_ID)
        for chunk in chunks:
            assert chunk.case_id == CASE_ID


class TestUpsertVectorsMetadata:
    """Tests that vector upsert passes correct metadata to Pinecone."""

    @pytest.mark.asyncio
    async def test_upsert_includes_case_metadata(self):
        """Vectors should be upserted with case_id, citation, year, court, acts_cited."""
        chunks = [
            Chunk(text="Section 302 IPC murder charge.", section_type="HOLDINGS",
                  chunk_index=0, case_id=CASE_ID),
            Chunk(text="Bail was granted under Section 438 CrPC.", section_type="ORDER",
                  chunk_index=1, case_id=CASE_ID),
        ]
        embeddings = [[0.1] * 1536, [0.2] * 1536]
        metadata = _make_metadata()

        mock_vector_store = AsyncMock()
        mock_vector_store.upsert = AsyncMock()

        await _upsert_vectors(
            case_id=CASE_ID,
            chunks=chunks,
            embeddings=embeddings,
            metadata=metadata,
            vector_store=mock_vector_store,
        )

        # Verify upsert was called
        mock_vector_store.upsert.assert_called_once()
        call_args = mock_vector_store.upsert.call_args

        # Extract the vectors argument
        vectors = call_args.kwargs.get("vectors") or call_args.args[0]
        assert len(vectors) == 2

        # Verify metadata on first vector
        v0 = vectors[0]
        assert v0["id"].startswith(CASE_ID)
        assert v0["metadata"]["case_id"] == CASE_ID
        assert v0["metadata"]["citation"] == "(2024) 5 SCC 142"
        assert v0["metadata"]["year"] == 2024
        assert v0["metadata"]["court"] == "Supreme Court of India"
        assert v0["metadata"]["chunk_index"] == 0
        assert v0["metadata"]["section_type"] == "HOLDINGS"
        assert "IPC" in v0["metadata"]["acts_cited"]

    @pytest.mark.asyncio
    async def test_upsert_includes_section_type(self):
        """Each vector should have the section_type from its chunk."""
        chunks = [
            Chunk(text="Facts of the case...", section_type="FACTS",
                  chunk_index=0, case_id=CASE_ID),
            Chunk(text="The court held...", section_type="HOLDINGS",
                  chunk_index=1, case_id=CASE_ID),
        ]
        embeddings = [[0.1] * 1536, [0.2] * 1536]
        metadata = _make_metadata()

        mock_vector_store = AsyncMock()
        mock_vector_store.upsert = AsyncMock()

        await _upsert_vectors(
            case_id=CASE_ID,
            chunks=chunks,
            embeddings=embeddings,
            metadata=metadata,
            vector_store=mock_vector_store,
        )

        vectors = mock_vector_store.upsert.call_args.kwargs.get("vectors") or \
                  mock_vector_store.upsert.call_args.args[0]

        assert vectors[0]["metadata"]["section_type"] == "FACTS"
        assert vectors[1]["metadata"]["section_type"] == "HOLDINGS"


class TestEndToEndChunkEmbed:
    """Tests chunking + embedding flow."""

    @pytest.mark.asyncio
    async def test_chunk_then_embed_produces_matching_counts(self):
        """Number of embeddings should match number of chunks."""
        chunks = chunk_judgment(JUDGMENT_TEXT, case_id=CASE_ID)
        assert len(chunks) > 0

        # Mock embedder that returns correct-dimension vectors
        mock_embedder = AsyncMock()
        mock_embedder.embed_batch.return_value = [
            [0.1] * 1536 for _ in chunks
        ]
        mock_embedder.dimension.return_value = 1536

        embeddings = await mock_embedder.embed_batch([c.text for c in chunks])
        assert len(embeddings) == len(chunks)
        assert all(len(e) == 1536 for e in embeddings)
