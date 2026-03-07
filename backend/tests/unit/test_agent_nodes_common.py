"""Tests for agent node common utilities."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.agents.nodes.common import (
    enrich_results_with_ratio,
    format_search_results_for_llm,
    verify_case_ids,
)


# ---------------------------------------------------------------------------
# format_search_results_for_llm
# ---------------------------------------------------------------------------


class TestFormatSearchResultsForLlm:
    def test_empty_results_returns_no_results_message(self) -> None:
        assert format_search_results_for_llm([]) == "No results found."

    def test_single_result_formatted_correctly(self) -> None:
        results = [
            {
                "title": "State v. Sharma",
                "citation": "(2023) 5 SCC 100",
                "court": "Supreme Court of India",
                "year": 2023,
                "snippet": "The court held that fundamental rights are paramount.",
            }
        ]
        output = format_search_results_for_llm(results)
        assert "[1]" in output
        assert "State v. Sharma" in output
        assert "(2023) 5 SCC 100" in output
        assert "Supreme Court of India" in output
        assert "2023" in output
        assert "fundamental rights are paramount" in output

    def test_multiple_results_numbered(self) -> None:
        results = [
            {"title": f"Case {i}", "citation": f"cite-{i}", "court": "SC", "year": 2020, "snippet": "x"}
            for i in range(3)
        ]
        output = format_search_results_for_llm(results)
        assert "[1]" in output
        assert "[2]" in output
        assert "[3]" in output

    def test_snippet_truncated_to_max_len(self) -> None:
        long_snippet = "A" * 1000
        results = [{"title": "T", "snippet": long_snippet}]
        output = format_search_results_for_llm(results, max_snippet_len=50)
        # The snippet in output should be at most 50 chars of A
        assert "A" * 50 in output
        assert "A" * 51 not in output

    def test_missing_fields_use_defaults(self) -> None:
        results = [{}]
        output = format_search_results_for_llm(results)
        assert "Untitled" in output
        assert "No citation" in output
        assert "Unknown" in output

    def test_none_snippet_handled(self) -> None:
        results = [{"title": "T", "snippet": None}]
        output = format_search_results_for_llm(results)
        assert "T" in output


# ---------------------------------------------------------------------------
# format_search_results_for_llm — enriched fields
# ---------------------------------------------------------------------------


class TestFormatSearchResultsEnriched:
    def test_includes_ratio_field(self) -> None:
        results = [
            {
                "title": "State v. Kumar",
                "citation": "(2022) 3 SCC 50",
                "court": "Supreme Court of India",
                "year": 2022,
                "snippet": "Brief passage.",
                "ratio": "The principle of natural justice must be followed in all quasi-judicial proceedings.",
            }
        ]
        output = format_search_results_for_llm(results)
        assert "Ratio Decidendi:" in output
        assert "natural justice" in output

    def test_includes_bench_type(self) -> None:
        results = [
            {
                "title": "Union v. Rao",
                "citation": "(2021) 1 SCC 200",
                "court": "Supreme Court of India",
                "year": 2021,
                "snippet": "Some text.",
                "bench_type": "division",
            }
        ]
        output = format_search_results_for_llm(results)
        assert "Division Bench" in output
        assert "Supreme Court of India (Division Bench)" in output

    def test_no_ratio_still_works(self) -> None:
        results = [
            {
                "title": "A v. B",
                "citation": "(2020) 2 SCC 10",
                "court": "High Court",
                "year": 2020,
                "snippet": "The court observed something.",
            }
        ]
        output = format_search_results_for_llm(results)
        assert "Ratio Decidendi:" not in output
        assert "Relevant Passage:" in output
        assert "The court observed something." in output


# ---------------------------------------------------------------------------
# enrich_results_with_ratio
# ---------------------------------------------------------------------------


class TestEnrichResultsWithRatio:
    @pytest.mark.asyncio
    async def test_enriches_results_with_ratio(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("case-1", "Natural justice applies to all tribunals.", "division"),
        ]
        db = AsyncMock()
        db.execute.return_value = mock_result

        results = [{"case_id": "case-1", "title": "Test Case"}]
        enriched = await enrich_results_with_ratio(results, db)

        assert enriched[0]["ratio"] == "Natural justice applies to all tribunals."
        assert enriched[0]["bench_type"] == "division"

    @pytest.mark.asyncio
    async def test_enriches_bench_type(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("case-2", "", "constitutional"),
        ]
        db = AsyncMock()
        db.execute.return_value = mock_result

        results = [{"case_id": "case-2", "title": "Bench Case"}]
        enriched = await enrich_results_with_ratio(results, db)

        assert enriched[0]["bench_type"] == "constitutional"

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty(self) -> None:
        db = AsyncMock()
        enriched = await enrich_results_with_ratio([], db)
        assert enriched == []
        db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# verify_case_ids
# ---------------------------------------------------------------------------


class TestVerifyCaseIds:
    @pytest.mark.asyncio
    async def test_empty_list_returns_empty_set(self) -> None:
        db = AsyncMock()
        result = await verify_case_ids([], db)
        assert result == set()
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_existing_ids(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("id-1",), ("id-3",)]
        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await verify_case_ids(["id-1", "id-2", "id-3"], db)
        assert result == {"id-1", "id-3"}
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_matches_returns_empty_set(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await verify_case_ids(["id-999"], db)
        assert result == set()
