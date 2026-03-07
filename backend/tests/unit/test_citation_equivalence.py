"""Tests for citation equivalence search integration."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.search.hybrid import _exact_citation_search


class TestExactCitationSearch:
    @pytest.mark.asyncio
    async def test_returns_results_for_matching_citation(self):
        """Should return results when citation matches in DB."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [{
            "id": "case-uuid-1",
            "title": "State v. XYZ",
            "citation": "(2023) 5 SCC 123",
            "court": "Supreme Court of India",
            "year": 2023,
            "decision_date": "2023-01-15",
            "case_type": "Criminal Appeal",
            "judge": ["Justice A"],
            "bench_type": "division",
        }]
        mock_db.execute.return_value = mock_result

        results = await _exact_citation_search("(2023) 5 SCC 123", mock_db)
        assert len(results) == 1
        assert results[0].citation == "(2023) 5 SCC 123"

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_match(self):
        """Should return empty list when no citation matches."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        results = await _exact_citation_search("NONEXISTENT 2099 XX 999", mock_db)
        assert results == []

    @pytest.mark.asyncio
    async def test_also_checks_equivalents_table(self):
        """Should also check case_citation_equivalents for cross-format matches."""
        mock_db = AsyncMock()
        # First call (cases table) returns empty
        mock_empty = MagicMock()
        mock_empty.mappings.return_value.all.return_value = []
        # Second call (equivalents table) returns a match
        mock_found = MagicMock()
        mock_found.mappings.return_value.all.return_value = [{
            "id": "case-uuid-1",
            "title": "Kesavananda Bharati",
            "citation": "(1973) 4 SCC 225",
            "court": "Supreme Court of India",
            "year": 1973,
            "decision_date": "1973-04-24",
            "case_type": "Writ Petition",
            "judge": None,
            "bench_type": "constitutional",
        }]
        mock_db.execute.side_effect = [mock_empty, mock_found]

        results = await _exact_citation_search("AIR 1973 SC 1461", mock_db)
        assert len(results) >= 1
