"""Tests for agent node common utilities."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.agents.nodes.common import format_search_results_for_llm, verify_case_ids


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
