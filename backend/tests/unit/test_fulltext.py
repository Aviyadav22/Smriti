"""Unit tests for PostgreSQL FTS filter construction."""

import pytest

from app.core.search.fulltext import _build_filter_clauses
from app.core.search.query import SearchFilters


class TestBuildFilterClauses:
    """Test the SQL filter builder — pure function, no DB needed."""

    def test_no_filters(self) -> None:
        """None filters returns empty clauses."""
        clauses, params = _build_filter_clauses(None)
        assert clauses == []
        assert params == {}

    def test_empty_filters(self) -> None:
        """Default SearchFilters (all None) returns empty clauses."""
        clauses, params = _build_filter_clauses(SearchFilters())
        assert clauses == []
        assert params == {}

    def test_court_filter(self) -> None:
        filters = SearchFilters(court="Supreme Court")
        clauses, params = _build_filter_clauses(filters)
        assert len(clauses) == 1
        assert "court ILIKE :court" in clauses[0]
        assert "%Supreme Court%" in params["court"]

    def test_year_range_filter(self) -> None:
        filters = SearchFilters(year_from=2015, year_to=2024)
        clauses, params = _build_filter_clauses(filters)
        assert len(clauses) == 2
        assert params["year_from"] == 2015
        assert params["year_to"] == 2024

    def test_year_from_only(self) -> None:
        filters = SearchFilters(year_from=2020)
        clauses, params = _build_filter_clauses(filters)
        assert len(clauses) == 1
        assert "year >= :year_from" in clauses[0]

    def test_case_type_filter(self) -> None:
        filters = SearchFilters(case_type="Criminal Appeal")
        clauses, params = _build_filter_clauses(filters)
        assert "case_type ILIKE :case_type" in clauses[0]
        assert "%Criminal Appeal%" in params["case_type"]

    def test_bench_type_filter(self) -> None:
        filters = SearchFilters(bench_type="division")
        clauses, params = _build_filter_clauses(filters)
        assert "bench_type = :bench_type" in clauses[0]
        assert params["bench_type"] == "division"

    def test_judge_filter(self) -> None:
        filters = SearchFilters(judge="Chandrachud")
        clauses, params = _build_filter_clauses(filters)
        assert "ILIKE :judge" in clauses[0]
        assert "%Chandrachud%" in params["judge"]

    def test_act_filter(self) -> None:
        filters = SearchFilters(act="Indian Penal Code")
        clauses, params = _build_filter_clauses(filters)
        assert "ILIKE :act" in clauses[0]

    def test_all_filters_combined(self) -> None:
        """All filters produce separate clauses."""
        filters = SearchFilters(
            court="Supreme Court",
            year_from=2015,
            year_to=2024,
            case_type="Criminal Appeal",
            bench_type="division",
            judge="Chandrachud",
            act="IPC",
        )
        clauses, params = _build_filter_clauses(filters)
        assert len(clauses) == 7
        assert len(params) == 7
