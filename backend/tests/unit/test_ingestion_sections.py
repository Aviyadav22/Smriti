"""Tests for section extraction and citation equivalent population during ingestion."""

from app.core.ingestion.pipeline import _extract_citation_equivalents


class TestExtractCitationEquivalents:
    def test_extracts_scc_citation(self):
        text = "This case is reported as (2023) 5 SCC 123."
        results = _extract_citation_equivalents(text, "case-uuid")
        reporters = [r["reporter"] for r in results]
        assert "SCC" in reporters

    def test_extracts_air_citation(self):
        text = "Also cited as AIR 2023 SC 456."
        results = _extract_citation_equivalents(text, "case-uuid")
        reporters = [r["reporter"] for r in results]
        assert "AIR" in reporters

    def test_extracts_multiple_formats(self):
        text = "(2023) 5 SCC 123 is also reported as AIR 2023 SC 456."
        results = _extract_citation_equivalents(text, "case-uuid")
        assert len(results) >= 2

    def test_empty_text_returns_empty(self):
        results = _extract_citation_equivalents("", "case-uuid")
        assert results == []
