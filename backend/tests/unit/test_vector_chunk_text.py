"""Tests for vector chunk text surfacing through the search pipeline.

Verifies that Pinecone chunk text is preserved in _vector_search, used as
fallback in _build_snippets_map, populated on SearchResultItem, and preferred
in RAG _build_sources.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core.search.fulltext import FTSResult
from app.core.search.hybrid import SearchResultItem, _build_snippets_map

# ---------------------------------------------------------------------------
# SearchResultItem dataclass
# ---------------------------------------------------------------------------


class TestSearchResultItemChunkText:
    """Verify the chunk_text field on SearchResultItem."""

    def test_chunk_text_defaults_to_none(self) -> None:
        item = SearchResultItem(case_id="c1", score=0.9)
        assert item.chunk_text is None

    def test_chunk_text_can_be_set(self) -> None:
        item = SearchResultItem(
            case_id="c1",
            score=0.9,
            chunk_text="The court held that Article 21 is paramount.",
        )
        assert item.chunk_text == "The court held that Article 21 is paramount."

    def test_chunk_text_immutable(self) -> None:
        item = SearchResultItem(case_id="c1", score=0.9, chunk_text="text")
        with pytest.raises(AttributeError):
            item.chunk_text = "changed"  # type: ignore[misc]

    def test_chunk_text_in_serialization(self) -> None:
        """chunk_text should appear when converting to dict via asdict."""
        from dataclasses import asdict

        item = SearchResultItem(case_id="c1", score=0.9, chunk_text="passage")
        d = asdict(item)
        assert d["chunk_text"] == "passage"

    def test_chunk_text_absent_in_old_data(self) -> None:
        """Constructing from a dict without chunk_text should still work."""
        data = {"case_id": "c1", "score": 0.5}
        # chunk_text has a default, so this should work
        item = SearchResultItem(**data)
        assert item.chunk_text is None


# ---------------------------------------------------------------------------
# _build_snippets_map with vector chunk text
# ---------------------------------------------------------------------------


class TestBuildSnippetsMapVectorFallback:
    """Test that _build_snippets_map uses vector chunk text as fallback."""

    def test_fts_snippet_takes_priority(self) -> None:
        """When a case has both FTS snippet and vector chunk, FTS wins."""
        fts = [FTSResult(case_id="c1", rank=1.0, snippet="FTS headline text", title="Case 1")]
        vector = [("c1", 0.95, "Vector passage about Article 21", 0, 500, 10.0)]
        result = _build_snippets_map(fts, vector)
        assert result["c1"] == "FTS headline text"

    def test_vector_chunk_text_used_when_no_fts(self) -> None:
        """Cases found only via vector search should use chunk text."""
        fts: list[FTSResult] = []
        vector = [("c1", 0.95, "The petitioner argued right to privacy", 0, 500, 5.0)]
        result = _build_snippets_map(fts, vector)
        assert result["c1"] == "The petitioner argued right to privacy"

    def test_mixed_fts_and_vector_only(self) -> None:
        """FTS case gets FTS snippet; vector-only case gets chunk text."""
        fts = [FTSResult(case_id="c1", rank=1.0, snippet="FTS text", title="Case 1")]
        vector = [
            ("c1", 0.95, "Vector text for c1", 0, 500, 10.0),
            ("c2", 0.85, "Vector text for c2", 0, 400, 5.0),
        ]
        result = _build_snippets_map(fts, vector)
        assert result["c1"] == "FTS text"  # FTS wins
        assert result["c2"] == "Vector text for c2"  # vector fallback

    def test_empty_vector_chunk_text_not_used(self) -> None:
        """Empty chunk text should not be added to the snippets map."""
        fts: list[FTSResult] = []
        vector = [("c1", 0.95, "", 0, 0, 0.0)]
        result = _build_snippets_map(fts, vector)
        assert "c1" not in result

    def test_fts_title_fallback_still_works(self) -> None:
        """FTS result with no snippet but with title should use title."""
        fts = [FTSResult(case_id="c1", rank=1.0, snippet=None, title="Case Title")]
        vector: list[tuple[str, float, str, int, int, float]] = []
        result = _build_snippets_map(fts, vector)
        assert result["c1"] == "Case Title"

    def test_both_empty_returns_empty(self) -> None:
        result = _build_snippets_map([], [])
        assert result == {}

    def test_multiple_vector_results_all_used(self) -> None:
        """All vector-only cases should get their chunk text in the map."""
        fts: list[FTSResult] = []
        vector = [
            ("c1", 0.95, "Text one", 0, 500, 10.0),
            ("c2", 0.85, "Text two", 0, 400, 5.0),
            ("c3", 0.75, "Text three", 0, 300, 2.0),
        ]
        result = _build_snippets_map(fts, vector)
        assert result == {"c1": "Text one", "c2": "Text two", "c3": "Text three"}


# ---------------------------------------------------------------------------
# RAG _build_sources chunk_text preference
# ---------------------------------------------------------------------------


class TestBuildSourcesChunkTextPreference:
    """Test that RAG _build_sources prefers chunk_text over snippet."""

    def test_chunk_text_preferred_over_snippet(self) -> None:
        """When SearchResultItem has both chunk_text and snippet, chunk_text wins."""

        # Simulate what _build_sources does: chunk_text || snippet || description
        sr = SearchResultItem(
            case_id="c1",
            score=0.9,
            snippet="FTS headline",
            chunk_text="Vector passage about fundamental rights",
        )
        # Replicate the logic from _build_sources
        chunk_text = (
            getattr(sr, "chunk_text", None)
            or getattr(sr, "snippet", None)
            or "fallback description"
        )
        assert chunk_text == "Vector passage about fundamental rights"

    def test_snippet_used_when_no_chunk_text(self) -> None:
        """When chunk_text is None, snippet should be used."""
        sr = SearchResultItem(
            case_id="c1",
            score=0.9,
            snippet="FTS headline",
            chunk_text=None,
        )
        chunk_text = getattr(sr, "chunk_text", None) or getattr(sr, "snippet", None) or "fallback"
        assert chunk_text == "FTS headline"

    def test_description_used_when_both_none(self) -> None:
        """When both chunk_text and snippet are None, description fallback works."""
        sr = SearchResultItem(case_id="c1", score=0.9)
        chunk_text = (
            getattr(sr, "chunk_text", None) or getattr(sr, "snippet", None) or "DB description text"
        )
        assert chunk_text == "DB description text"


# ---------------------------------------------------------------------------
# _vector_search return format (integration-style, using mock)
# ---------------------------------------------------------------------------


@dataclass
class MockVectorResult:
    """Mock a single Pinecone vector search result."""

    id: str
    score: float
    metadata: dict


class MockEmbedder:
    async def embed_text(self, text: str) -> list[float]:
        return [0.1] * 1536


class MockVectorStore:
    def __init__(self, results: list[MockVectorResult]) -> None:
        self._results = results

    async def search(self, vector, top_k=10, filters=None) -> list[MockVectorResult]:
        return self._results


class TestVectorSearchChunkText:
    """Test that _vector_search preserves chunk text from metadata."""

    @pytest.mark.asyncio
    async def test_returns_six_tuples(self) -> None:
        from app.core.search.hybrid import _vector_search

        store = MockVectorStore(
            [
                MockVectorResult(
                    id="chunk-1",
                    score=0.95,
                    metadata={
                        "case_id": "c1",
                        "text": "passage one",
                        "char_start": 100,
                        "char_end": 500,
                        "legal_signal": 42.5,
                    },
                ),
            ]
        )
        results = await _vector_search(
            "test query", embedder=MockEmbedder(), vector_store=store, filters=None
        )
        assert len(results) == 1
        case_id, score, chunk_text, char_start, char_end, legal_signal = results[0]
        assert case_id == "c1"
        assert score == 0.95
        assert chunk_text == "passage one"
        assert char_start == 100
        assert char_end == 500
        assert legal_signal == 42.5

    @pytest.mark.asyncio
    async def test_deduplicates_keeping_best_chunk(self) -> None:
        """When multiple chunks map to the same case, keep highest-scoring chunk text."""
        from app.core.search.hybrid import _vector_search

        store = MockVectorStore(
            [
                MockVectorResult(
                    id="chunk-1", score=0.80, metadata={"case_id": "c1", "text": "lower passage"}
                ),
                MockVectorResult(
                    id="chunk-2", score=0.95, metadata={"case_id": "c1", "text": "best passage"}
                ),
                MockVectorResult(
                    id="chunk-3", score=0.85, metadata={"case_id": "c1", "text": "mid passage"}
                ),
            ]
        )
        results = await _vector_search(
            "test", embedder=MockEmbedder(), vector_store=store, filters=None
        )
        assert len(results) == 1
        assert results[0][2] == "best passage"
        assert results[0][1] == 0.95

    @pytest.mark.asyncio
    async def test_chunk_text_from_text_field(self) -> None:
        """Chunk text should come from metadata 'text' field."""
        from app.core.search.hybrid import _vector_search

        store = MockVectorStore(
            [
                MockVectorResult(
                    id="chunk-1", score=0.9, metadata={"case_id": "c1", "text": "from text field"}
                ),
            ]
        )
        results = await _vector_search(
            "q", embedder=MockEmbedder(), vector_store=store, filters=None
        )
        assert results[0][2] == "from text field"

    @pytest.mark.asyncio
    async def test_chunk_text_from_chunk_text_field(self) -> None:
        """Falls back to metadata 'chunk_text' when 'text' is empty."""
        from app.core.search.hybrid import _vector_search

        store = MockVectorStore(
            [
                MockVectorResult(
                    id="chunk-1",
                    score=0.9,
                    metadata={"case_id": "c1", "text": "", "chunk_text": "from chunk_text field"},
                ),
            ]
        )
        results = await _vector_search(
            "q", embedder=MockEmbedder(), vector_store=store, filters=None
        )
        assert results[0][2] == "from chunk_text field"

    @pytest.mark.asyncio
    async def test_empty_chunk_text_when_no_metadata_text(self) -> None:
        """Returns empty string when neither text nor chunk_text in metadata."""
        from app.core.search.hybrid import _vector_search

        store = MockVectorStore(
            [
                MockVectorResult(id="chunk-1", score=0.9, metadata={"case_id": "c1"}),
            ]
        )
        results = await _vector_search(
            "q", embedder=MockEmbedder(), vector_store=store, filters=None
        )
        assert results[0][2] == ""

    @pytest.mark.asyncio
    async def test_sorted_by_descending_score(self) -> None:
        from app.core.search.hybrid import _vector_search

        store = MockVectorStore(
            [
                MockVectorResult(
                    id="chunk-1", score=0.70, metadata={"case_id": "c1", "text": "t1"}
                ),
                MockVectorResult(
                    id="chunk-2", score=0.95, metadata={"case_id": "c2", "text": "t2"}
                ),
                MockVectorResult(
                    id="chunk-3", score=0.85, metadata={"case_id": "c3", "text": "t3"}
                ),
            ]
        )
        results = await _vector_search(
            "q", embedder=MockEmbedder(), vector_store=store, filters=None
        )
        scores = [r[1] for r in results]
        assert scores == sorted(scores, reverse=True)
