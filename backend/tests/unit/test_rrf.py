"""Unit tests for Reciprocal Rank Fusion (RRF) merge function."""

import pytest

from app.core.search.hybrid import rrf_merge


class TestRRFMerge:
    """Test the pure rrf_merge function."""

    def test_two_lists_with_overlap(self) -> None:
        """Docs appearing in both lists get higher scores."""
        vector = [("doc_a", 0.95), ("doc_b", 0.90), ("doc_c", 0.85)]
        fts = [("doc_b", 5.0), ("doc_a", 4.0), ("doc_d", 3.0)]

        result = rrf_merge([vector, fts], k=60)
        ids = [doc_id for doc_id, _ in result]

        # doc_a and doc_b appear in both, should be top-ranked
        assert ids[0] in ("doc_a", "doc_b")
        assert ids[1] in ("doc_a", "doc_b")
        # All 4 docs should appear
        assert len(result) == 4
        assert set(ids) == {"doc_a", "doc_b", "doc_c", "doc_d"}

    def test_rrf_scores_are_correct(self) -> None:
        """Verify exact RRF score calculation."""
        list1 = [("doc_a", 1.0), ("doc_b", 0.5)]
        list2 = [("doc_b", 1.0), ("doc_a", 0.5)]

        result = rrf_merge([list1, list2], k=60)
        scores = {doc_id: score for doc_id, score in result}

        # Both docs at rank 1 and 2 across two lists
        # doc_a: 1/(60+1) + 1/(60+2) = 1/61 + 1/62
        # doc_b: 1/(60+2) + 1/(60+1) = 1/62 + 1/61
        expected = 1 / 61 + 1 / 62
        assert abs(scores["doc_a"] - expected) < 1e-10
        assert abs(scores["doc_b"] - expected) < 1e-10

    def test_single_list_passthrough(self) -> None:
        """Single list returns docs in original order."""
        single = [("doc_x", 0.9), ("doc_y", 0.8), ("doc_z", 0.7)]
        result = rrf_merge([single], k=60)
        ids = [doc_id for doc_id, _ in result]

        assert ids == ["doc_x", "doc_y", "doc_z"]

    def test_empty_lists(self) -> None:
        """Empty input returns empty output."""
        assert rrf_merge([]) == []
        assert rrf_merge([[]]) == []
        assert rrf_merge([[], []]) == []

    def test_disjoint_lists(self) -> None:
        """Disjoint lists include all docs."""
        list1 = [("a", 1.0), ("b", 0.5)]
        list2 = [("c", 1.0), ("d", 0.5)]

        result = rrf_merge([list1, list2], k=60)
        ids = {doc_id for doc_id, _ in result}
        assert ids == {"a", "b", "c", "d"}

    def test_custom_k_value(self) -> None:
        """Different k values produce different (but valid) rankings."""
        ranked = [("a", 1.0), ("b", 0.5)]
        result_k1 = rrf_merge([ranked], k=1)
        result_k100 = rrf_merge([ranked], k=100)

        # Both should have same order
        assert [i for i, _ in result_k1] == [i for i, _ in result_k100]

        # k=1: scores are 1/2 and 1/3; k=100: scores are 1/101 and 1/102
        score_a_k1 = dict(result_k1)["a"]
        score_a_k100 = dict(result_k100)["a"]
        assert score_a_k1 > score_a_k100

    def test_three_lists(self) -> None:
        """Three lists merge correctly."""
        list1 = [("a", 1.0)]
        list2 = [("a", 1.0), ("b", 0.5)]
        list3 = [("b", 1.0), ("a", 0.5), ("c", 0.3)]

        result = rrf_merge([list1, list2, list3], k=60)
        ids = [i for i, _ in result]

        # "a" appears in all 3 lists, should be first
        assert ids[0] == "a"
        assert len(ids) == 3

    def test_sorted_by_descending_score(self) -> None:
        """Results are always sorted by descending RRF score."""
        ranked = [("z", 1.0), ("y", 0.9), ("x", 0.8), ("w", 0.7)]
        result = rrf_merge([ranked], k=60)
        scores = [s for _, s in result]
        assert scores == sorted(scores, reverse=True)
