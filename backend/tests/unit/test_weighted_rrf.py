"""Tests for weighted RRF merge and search strategy routing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.search.hybrid import (
    SearchResultItem,
    _exact_citation_search,
    rrf_merge,
)

# ---------------------------------------------------------------------------
# rrf_merge tests
# ---------------------------------------------------------------------------


class TestRRFMerge:
    """Tests for the rrf_merge function with optional weights."""

    def _make_list(self, ids: list[str]) -> list[tuple[str, float]]:
        """Helper to build a ranked list with dummy scores."""
        return [(doc_id, 1.0 / (i + 1)) for i, doc_id in enumerate(ids)]

    def test_equal_weights_matches_unweighted(self) -> None:
        """Default weights [1.0, 1.0] produce identical results to no weights."""
        list_a = self._make_list(["a", "b", "c"])
        list_b = self._make_list(["b", "c", "d"])

        unweighted = rrf_merge([list_a, list_b], k=60)
        weighted = rrf_merge([list_a, list_b], k=60, weights=[1.0, 1.0])

        assert unweighted == weighted

    def test_double_weight_boosts_list(self) -> None:
        """A 2x weight on list_a should boost items exclusive to list_a."""
        # "x" appears only in list_a, "y" only in list_b, both at rank 1
        list_a = self._make_list(["x"])
        list_b = self._make_list(["y"])

        result = rrf_merge([list_a, list_b], k=60, weights=[2.0, 1.0])
        result_dict = dict(result)

        # "x" should have double the score of "y"
        assert result_dict["x"] == pytest.approx(result_dict["y"] * 2.0)
        # "x" should be ranked first
        assert result[0][0] == "x"

    def test_zero_weight_excludes_list(self) -> None:
        """A weight of 0 means that list contributes nothing."""
        list_a = self._make_list(["a", "b"])
        list_b = self._make_list(["c", "d"])

        result = rrf_merge([list_a, list_b], k=60, weights=[1.0, 0.0])
        result_dict = dict(result)

        # list_b items should have zero score
        assert result_dict.get("c", 0.0) == 0.0
        assert result_dict.get("d", 0.0) == 0.0
        # list_a items should have non-zero scores
        assert result_dict["a"] > 0.0
        assert result_dict["b"] > 0.0

    def test_weights_length_mismatch_raises(self) -> None:
        """Passing wrong number of weights should raise ValueError."""
        list_a = self._make_list(["a"])
        list_b = self._make_list(["b"])

        with pytest.raises(ValueError, match="weights length"):
            rrf_merge([list_a, list_b], k=60, weights=[1.0])

        with pytest.raises(ValueError, match="weights length"):
            rrf_merge([list_a, list_b], k=60, weights=[1.0, 1.0, 1.0])

    def test_empty_lists(self) -> None:
        """Empty ranked lists should return empty result."""
        result = rrf_merge([], k=60)
        assert result == []

    def test_single_list_with_weight(self) -> None:
        """A single list with weight 3.0 should triple scores vs weight 1.0."""
        ranked = self._make_list(["a", "b"])

        base = rrf_merge([ranked], k=60, weights=[1.0])
        boosted = rrf_merge([ranked], k=60, weights=[3.0])

        base_dict = dict(base)
        boosted_dict = dict(boosted)

        for doc_id in ["a", "b"]:
            assert boosted_dict[doc_id] == pytest.approx(base_dict[doc_id] * 3.0)


# ---------------------------------------------------------------------------
# _exact_citation_search tests
# ---------------------------------------------------------------------------


class TestExactCitationSearch:
    """Tests for the _exact_citation_search helper."""

    @pytest.mark.asyncio
    async def test_search_strategy_exact_match(self) -> None:
        """_exact_citation_search returns SearchResultItem list from DB rows."""
        # Build a mock AsyncSession
        mock_row = {
            "id": "case-123",
            "title": "State of UP v. Ram",
            "citation": "(2020) 5 SCC 1",
            "court": "Supreme Court of India",
            "year": 2020,
            "decision_date": "2020-03-15",
            "case_type": "Criminal Appeal",
            "judge": "Justice A",
            "bench_type": "Division Bench",
        }

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [mock_row]

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        results = await _exact_citation_search("(2020) 5 SCC 1", mock_db)

        assert len(results) == 1
        r = results[0]
        assert isinstance(r, SearchResultItem)
        assert r.case_id == "case-123"
        assert r.citation == "(2020) 5 SCC 1"
        assert r.score == 1.0
        assert r.bench_type == "Division Bench"
        assert r.court == "Supreme Court of India"

    @pytest.mark.asyncio
    async def test_exact_match_no_results(self) -> None:
        """_exact_citation_search returns empty list when nothing matches."""
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        results = await _exact_citation_search("nonexistent citation", mock_db)
        assert results == []
