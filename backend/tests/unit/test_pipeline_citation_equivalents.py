"""Tests for cross-citation equivalence in the pipeline (G19).

Tests _extract_citation_equivalents and _link_citation_equivalents
from the ingestion pipeline.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.ingestion.pipeline import (
    _extract_citation_equivalents,
    _link_citation_equivalents,
)


class TestExtractCitationEquivalents:
    """G19: Tests for extracting parallel citations from judgment headers."""

    def test_extracts_scc_citation_from_header(self):
        """Should extract SCC citations from the header section."""
        header = (
            "IN THE SUPREME COURT OF INDIA\n"
            "Reported as (2017) 10 SCC 1\n"
            "Also reported as AIR 2017 SC 4161\n"
            "The judgment was delivered on 24th August 2017.\n"
        )
        full_text = header + "A" * 5000  # pad to simulate long judgment
        results = _extract_citation_equivalents(full_text, "case-001")
        assert len(results) >= 2
        citations = [r["citation_text"] for r in results]
        assert any("SCC" in c for c in citations)
        assert any("AIR" in c for c in citations)

    def test_only_header_citations_extracted(self):
        """Citations deep in the body should NOT be extracted as equivalents."""
        header = "(2017) 10 SCC 1\n"
        body = (
            "The court in (2005) 3 SCC 100 held that...\n"
            "Also see AIR 2010 SC 500 for similar reasoning.\n"
        ) * 50  # body citations
        full_text = header + "A" * 2500 + body  # body starts after 2000+ chars
        results = _extract_citation_equivalents(full_text, "case-001")
        # Should only get the header citation
        citations = [r["citation_text"] for r in results]
        assert any("(2017) 10 SCC 1" in c for c in citations)
        # Body citations should not be included (they're past 2000 chars)
        assert not any("(2005) 3 SCC 100" in c for c in citations)

    def test_empty_text_returns_empty(self):
        """Empty text should return empty list."""
        assert _extract_citation_equivalents("", "case-001") == []

    def test_no_citations_returns_empty(self):
        """Text without citations should return empty list."""
        text = "IN THE SUPREME COURT OF INDIA\nJUDGMENT\nThe facts are simple."
        assert _extract_citation_equivalents(text, "case-001") == []

    def test_result_structure(self):
        """Each result should have case_id, reporter, citation_text, year."""
        text = "(2020) 5 SCC 200\n" + "A" * 2000
        results = _extract_citation_equivalents(text, "case-xyz")
        assert len(results) >= 1
        r = results[0]
        assert r["case_id"] == "case-xyz"
        assert "reporter" in r
        assert "citation_text" in r
        assert "year" in r


class TestLinkCitationEquivalents:
    """G19: Tests for linking equivalent citations in Neo4j."""

    @pytest.mark.asyncio
    async def test_creates_equivalent_to_edges(self):
        """Should create EQUIVALENT_TO edges for non-primary citations."""
        graph_store = AsyncMock()
        graph_store.query = AsyncMock()

        equivalents = [
            {"citation_text": "(2017) 10 SCC 1"},
            {"citation_text": "AIR 2017 SC 4161"},
        ]

        await _link_citation_equivalents("case-001", "(2017) 10 SCC 1", equivalents, graph_store)

        # Should have been called (only for AIR citation, since primary is filtered out)
        graph_store.query.assert_called_once()
        call_args = graph_store.query.call_args
        assert "EQUIVALENT_TO" in call_args[0][0]
        assert call_args[1]["params"]["primary"] == "(2017) 10 SCC 1"

    @pytest.mark.asyncio
    async def test_skips_when_no_primary_citation(self):
        """Should do nothing when primary citation is None."""
        graph_store = AsyncMock()
        await _link_citation_equivalents("case-001", None, [{"citation_text": "x"}], graph_store)
        graph_store.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_no_equivalents(self):
        """Should do nothing when equivalents list is empty."""
        graph_store = AsyncMock()
        await _link_citation_equivalents("case-001", "(2020) 1 SCC 1", [], graph_store)
        graph_store.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_all_equivalents_match_primary(self):
        """Should do nothing when all equivalents are the same as primary."""
        graph_store = AsyncMock()
        equivalents = [{"citation_text": "(2020) 1 SCC 1"}]
        await _link_citation_equivalents("case-001", "(2020) 1 SCC 1", equivalents, graph_store)
        graph_store.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_graph_store_error_gracefully(self):
        """Graph store errors should be logged, not raised."""
        graph_store = AsyncMock()
        graph_store.query.side_effect = ConnectionError("Neo4j unavailable")

        equivalents = [{"citation_text": "AIR 2020 SC 100"}]
        # Should not raise
        await _link_citation_equivalents("case-001", "(2020) 1 SCC 1", equivalents, graph_store)
