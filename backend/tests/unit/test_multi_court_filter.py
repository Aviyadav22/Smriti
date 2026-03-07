"""Tests for multi-court filter support across search layers.

Verifies that SearchFilters.court accepts a list of court names and that
Pinecone filter construction, FTS clause building, and API parameter parsing
all handle single and multiple courts correctly.
"""

import pytest

from app.core.search.fulltext import _build_filter_clauses
from app.core.search.query import SearchFilters, _parse_llm_result


# ---------------------------------------------------------------------------
# SearchFilters dataclass
# ---------------------------------------------------------------------------


class TestSearchFiltersCourtType:
    """Verify court field is list[str] | None."""

    def test_court_default_none(self) -> None:
        filters = SearchFilters()
        assert filters.court is None

    def test_court_single_item_list(self) -> None:
        filters = SearchFilters(court=["Supreme Court of India"])
        assert filters.court == ["Supreme Court of India"]

    def test_court_multiple_items(self) -> None:
        filters = SearchFilters(
            court=["Supreme Court of India", "High Court of Delhi"]
        )
        assert len(filters.court) == 2
        assert "Supreme Court of India" in filters.court
        assert "High Court of Delhi" in filters.court


# ---------------------------------------------------------------------------
# Pinecone filter construction (_vector_search helper logic)
# ---------------------------------------------------------------------------


class TestPineconeFilterConstruction:
    """Test Pinecone filter dict built from SearchFilters.court."""

    @staticmethod
    def _build_pinecone_filter(filters: SearchFilters) -> dict:
        """Reproduce the filter construction logic from hybrid._vector_search."""
        pinecone_filter: dict = {}
        if filters.court:
            if len(filters.court) == 1:
                pinecone_filter["court"] = {"$eq": filters.court[0]}
            else:
                pinecone_filter["court"] = {"$in": filters.court}
        return pinecone_filter

    def test_no_court_filter(self) -> None:
        result = self._build_pinecone_filter(SearchFilters())
        assert "court" not in result

    def test_single_court_uses_eq(self) -> None:
        result = self._build_pinecone_filter(
            SearchFilters(court=["Supreme Court of India"])
        )
        assert result["court"] == {"$eq": "Supreme Court of India"}

    def test_multiple_courts_uses_in(self) -> None:
        courts = ["Supreme Court of India", "High Court of Delhi"]
        result = self._build_pinecone_filter(SearchFilters(court=courts))
        assert result["court"] == {"$in": courts}

    def test_three_courts_uses_in(self) -> None:
        courts = [
            "Supreme Court of India",
            "High Court of Delhi",
            "High Court of Bombay",
        ]
        result = self._build_pinecone_filter(SearchFilters(court=courts))
        assert result["court"] == {"$in": courts}
        assert len(result["court"]["$in"]) == 3


# ---------------------------------------------------------------------------
# FTS filter construction
# ---------------------------------------------------------------------------


class TestFTSMultiCourtFilter:
    """Test SQL WHERE clause construction for multiple courts."""

    def test_single_court_ilike(self) -> None:
        filters = SearchFilters(court=["Supreme Court"])
        clauses, params = _build_filter_clauses(filters)
        assert len(clauses) == 1
        assert "court ILIKE :court_0" in clauses[0]
        assert params["court_0"] == "%Supreme Court%"

    def test_two_courts_or_clause(self) -> None:
        filters = SearchFilters(
            court=["Supreme Court", "High Court of Delhi"]
        )
        clauses, params = _build_filter_clauses(filters)
        assert len(clauses) == 1
        # Should produce an OR clause
        assert "OR" in clauses[0]
        assert "court ILIKE :court_0" in clauses[0]
        assert "court ILIKE :court_1" in clauses[0]
        assert params["court_0"] == "%Supreme Court%"
        assert params["court_1"] == "%High Court of Delhi%"

    def test_three_courts_or_clause(self) -> None:
        courts = ["Supreme Court", "Delhi HC", "Bombay HC"]
        filters = SearchFilters(court=courts)
        clauses, params = _build_filter_clauses(filters)
        assert len(clauses) == 1
        for i in range(3):
            assert f"court ILIKE :court_{i}" in clauses[0]
            assert f"court_{i}" in params

    def test_multi_court_with_other_filters(self) -> None:
        filters = SearchFilters(
            court=["Supreme Court", "Delhi HC"],
            year_from=2020,
            case_type="Criminal Appeal",
        )
        clauses, params = _build_filter_clauses(filters)
        # court OR clause + year_from + case_type = 3 clauses
        assert len(clauses) == 3
        assert "court_0" in params
        assert "court_1" in params
        assert params["year_from"] == 2020

    def test_no_court_filter_unchanged(self) -> None:
        """No court filter should produce no court clause."""
        filters = SearchFilters(year_from=2020)
        clauses, params = _build_filter_clauses(filters)
        assert len(clauses) == 1
        assert "court" not in clauses[0]


# ---------------------------------------------------------------------------
# LLM result parsing wraps court string into list
# ---------------------------------------------------------------------------


class TestLLMCourtParsing:
    """Verify _parse_llm_result wraps LLM court string into a list."""

    def test_llm_court_string_wrapped_in_list(self) -> None:
        data = {
            "intent": "topic_search",
            "original_query": "test",
            "expanded_query": "test expanded",
            "filters": {"court": "Supreme Court of India"},
            "entities": {},
            "search_strategy": "balanced",
        }
        result = _parse_llm_result("test", data)
        assert result.filters.court == ["Supreme Court of India"]

    def test_llm_no_court_stays_none(self) -> None:
        data = {
            "intent": "general",
            "original_query": "test",
            "expanded_query": "test",
            "filters": {},
            "entities": {},
            "search_strategy": "balanced",
        }
        result = _parse_llm_result("test", data)
        assert result.filters.court is None

    def test_llm_empty_court_stays_none(self) -> None:
        data = {
            "intent": "general",
            "original_query": "test",
            "expanded_query": "test",
            "filters": {"court": ""},
            "entities": {},
            "search_strategy": "balanced",
        }
        result = _parse_llm_result("test", data)
        assert result.filters.court is None


# ---------------------------------------------------------------------------
# API route court parameter parsing
# ---------------------------------------------------------------------------


class TestCourtParamParsing:
    """Test comma-separated court string → list conversion (route logic)."""

    @staticmethod
    def _parse_court_param(court: str | None) -> list[str] | None:
        """Reproduce the parsing logic from search.py route."""
        return (
            [c.strip() for c in court.split(",") if c.strip()]
            if court
            else None
        )

    def test_none_returns_none(self) -> None:
        assert self._parse_court_param(None) is None

    def test_single_court(self) -> None:
        result = self._parse_court_param("Supreme Court of India")
        assert result == ["Supreme Court of India"]

    def test_two_courts_comma_separated(self) -> None:
        result = self._parse_court_param(
            "Supreme Court of India,High Court of Delhi"
        )
        assert result == ["Supreme Court of India", "High Court of Delhi"]

    def test_courts_with_spaces_around_commas(self) -> None:
        result = self._parse_court_param(
            "Supreme Court of India , High Court of Delhi"
        )
        assert result == ["Supreme Court of India", "High Court of Delhi"]

    def test_trailing_comma_ignored(self) -> None:
        result = self._parse_court_param("Supreme Court of India,")
        assert result == ["Supreme Court of India"]

    def test_empty_string_returns_none(self) -> None:
        assert self._parse_court_param("") is None
