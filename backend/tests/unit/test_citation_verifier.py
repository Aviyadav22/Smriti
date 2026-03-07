"""Tests for human-readable citation verification."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.agents.nodes.citation_verifier import (
    check_grounding,
    extract_citations_from_text,
    verify_citations_against_db,
)


# ---------------------------------------------------------------------------
# extract_citations_from_text
# ---------------------------------------------------------------------------


class TestExtractCitationsFromText:
    def test_extracts_scc_citation(self) -> None:
        text = "The court relied on (2017) 10 SCC 1 in its judgment."
        result = extract_citations_from_text(text)
        assert "(2017) 10 SCC 1" in result

    def test_extracts_air_citation(self) -> None:
        text = "As held in AIR 1978 SC 597, the right is fundamental."
        result = extract_citations_from_text(text)
        assert "AIR 1978 SC 597" in result

    def test_extracts_scc_online(self) -> None:
        text = "See 2023 SCC OnLine SC 456 for the latest position."
        result = extract_citations_from_text(text)
        assert "2023 SCC OnLine SC 456" in result

    def test_extracts_insc_citation(self) -> None:
        text = "The judgment reported as 2022 INSC 789 clarified this."
        result = extract_citations_from_text(text)
        assert "2022 INSC 789" in result

    def test_extracts_scr_citation(self) -> None:
        text = "Reported in [2019] 3 SCR 100, the court held..."
        result = extract_citations_from_text(text)
        assert "[2019] 3 SCR 100" in result

    def test_extracts_crlj_citation(self) -> None:
        text = "See 2020 CrLJ 145 for criminal procedure aspects."
        result = extract_citations_from_text(text)
        assert "2020 CrLJ 145" in result

    def test_extracts_scale_citation(self) -> None:
        text = "The order at (2021) 2 SCALE 300 was significant."
        result = extract_citations_from_text(text)
        assert "(2021) 2 SCALE 300" in result

    def test_no_citations(self) -> None:
        text = "This is plain text without any legal citations whatsoever."
        result = extract_citations_from_text(text)
        assert result == []

    def test_multiple_citations(self) -> None:
        text = (
            "The court in (2017) 10 SCC 1 and AIR 1978 SC 597 "
            "established the principle."
        )
        result = extract_citations_from_text(text)
        assert len(result) == 2

    def test_deduplicates_repeated_citations(self) -> None:
        text = (
            "First mention (2017) 10 SCC 1. "
            "Second mention (2017) 10 SCC 1."
        )
        result = extract_citations_from_text(text)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# verify_citations_against_db
# ---------------------------------------------------------------------------


class TestVerifyCitationsAgainstDb:
    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self) -> None:
        db = AsyncMock()
        verified, unverified = await verify_citations_against_db([], db)
        assert verified == []
        assert unverified == []

    @pytest.mark.asyncio
    async def test_found_in_cases_table(self) -> None:
        """Citation found in cases.citation should be verified."""
        db = AsyncMock()
        # First query (cases.citation) returns a match
        mock_result = MagicMock()
        mock_result.first.return_value = (1,)
        db.execute.return_value = mock_result

        verified, unverified = await verify_citations_against_db(
            ["(2017) 10 SCC 1"], db
        )
        assert "(2017) 10 SCC 1" in verified
        assert unverified == []

    @pytest.mark.asyncio
    async def test_found_in_equivalents_table(self) -> None:
        """Citation not in cases but in equivalents should be verified."""
        db = AsyncMock()

        # First call (cases.citation) returns None, second (equivalents) returns match
        no_match = MagicMock()
        no_match.first.return_value = None
        match = MagicMock()
        match.first.return_value = (1,)
        db.execute.side_effect = [no_match, match]

        verified, unverified = await verify_citations_against_db(
            ["AIR 1978 SC 597"], db
        )
        assert "AIR 1978 SC 597" in verified
        assert unverified == []

    @pytest.mark.asyncio
    async def test_not_found_is_unverified(self) -> None:
        """Citation not in either table should be unverified."""
        db = AsyncMock()
        no_match = MagicMock()
        no_match.first.return_value = None
        db.execute.return_value = no_match

        verified, unverified = await verify_citations_against_db(
            ["(2099) 1 SCC 999"], db
        )
        assert verified == []
        assert "(2099) 1 SCC 999" in unverified

    @pytest.mark.asyncio
    async def test_db_error_treated_as_unverified(self) -> None:
        """If DB query fails, the citation should be treated as unverified."""
        db = AsyncMock()
        db.execute.side_effect = ConnectionError("connection lost")

        verified, unverified = await verify_citations_against_db(
            ["(2017) 10 SCC 1"], db
        )
        assert verified == []
        assert "(2017) 10 SCC 1" in unverified


# ---------------------------------------------------------------------------
# check_grounding
# ---------------------------------------------------------------------------


class TestCheckGrounding:
    def test_flags_ungrounded_citation(self) -> None:
        """Citation in memo but not in search results should be flagged."""
        memo_citations = ["(2017) 10 SCC 1", "AIR 1978 SC 597"]
        search_citations = ["(2017) 10 SCC 1"]

        ungrounded = check_grounding(memo_citations, search_citations)
        assert "AIR 1978 SC 597" in ungrounded
        assert "(2017) 10 SCC 1" not in ungrounded

    def test_all_grounded(self) -> None:
        """When all memo citations appear in search results, no flags."""
        memo_citations = ["(2017) 10 SCC 1", "AIR 1978 SC 597"]
        search_citations = ["(2017) 10 SCC 1", "AIR 1978 SC 597"]

        ungrounded = check_grounding(memo_citations, search_citations)
        assert ungrounded == []

    def test_empty_memo_citations(self) -> None:
        ungrounded = check_grounding([], ["(2017) 10 SCC 1"])
        assert ungrounded == []

    def test_empty_search_citations(self) -> None:
        """If search had no citations, all memo citations are ungrounded."""
        memo_citations = ["(2017) 10 SCC 1"]
        ungrounded = check_grounding(memo_citations, [])
        assert len(ungrounded) == 1

    def test_normalization_handles_whitespace_differences(self) -> None:
        """Minor whitespace differences should not cause false positives."""
        memo_citations = ["(2017)  10  SCC  1"]  # extra spaces
        search_citations = ["(2017) 10 SCC 1"]

        ungrounded = check_grounding(memo_citations, search_citations)
        assert ungrounded == []
