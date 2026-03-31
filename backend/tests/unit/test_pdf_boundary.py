"""Tests for PDF boundary stripping."""

import pytest

from app.core.ingestion.pdf import _strip_leading_judgment_bleed


class TestStripLeadingJudgmentBleed:
    """Tests for boundary text removal."""

    def test_clean_text_unchanged(self):
        text = "IN THE SUPREME COURT OF INDIA\nCIVIL APPEAL NO. 123\nBody..."
        assert _strip_leading_judgment_bleed(text) == text

    def test_strips_leading_bleed_before_court_header(self):
        bleed = "...previous judgment conclusion. The appeal is dismissed.\n" * 5
        real = "IN THE SUPREME COURT OF INDIA\nCIVIL APPEAL NO. 123\nBody of judgment..."
        text = bleed + real
        result = _strip_leading_judgment_bleed(text)
        assert result.startswith("IN THE SUPREME COURT OF INDIA")
        assert "previous judgment conclusion" not in result

    def test_strips_bleed_before_reportable(self):
        bleed = "Some trailing text from previous case about damages.\n" * 5
        real = "REPORTABLE\nIN THE SUPREME COURT OF INDIA\nBody..."
        text = bleed + real
        result = _strip_leading_judgment_bleed(text)
        assert result.startswith("REPORTABLE")

    def test_strips_bleed_before_judgment_marker(self):
        bleed = "Tail of previous: ordered accordingly.\n" * 6
        real = "\nJUDGMENT\nThe facts of the case are..."
        text = bleed + real
        result = _strip_leading_judgment_bleed(text)
        assert "JUDGMENT" in result[:20]

    def test_no_marker_found_returns_unchanged(self):
        text = "This is some text without any case header markers at all. " * 20
        assert _strip_leading_judgment_bleed(text) == text

    def test_marker_within_first_200_chars_no_strip(self):
        """If the marker is near the start, there's no meaningful bleed."""
        text = "Short intro\nIN THE SUPREME COURT OF INDIA\nBody..."
        assert _strip_leading_judgment_bleed(text) == text

    def test_neutral_citation_as_marker(self):
        bleed = "End of previous case text about constitutional validity.\n" * 5
        real = "2023:INSC:456\nIN THE SUPREME COURT\nBody..."
        text = bleed + real
        result = _strip_leading_judgment_bleed(text)
        assert result.startswith("2023:INSC:456")

    def test_short_text_returns_unchanged(self):
        text = "Short"
        assert _strip_leading_judgment_bleed(text) == text
