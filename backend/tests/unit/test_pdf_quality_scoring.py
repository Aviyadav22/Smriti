"""Tests for PDF quality scoring and extract_and_score (G1, G2).

Covers score_text_quality tier logic, alpha_ratio enforcement,
chars-per-page enforcement, and extract_and_score OCR fallback path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.ingestion.pdf import (
    TextQuality,
    extract_and_score,
    score_text_quality,
)


class TestScoreTextQuality:
    """G1: Tests for score_text_quality()."""

    def test_high_tier_with_legal_text(self):
        """Long legal text with 3+ keywords should score 'high'."""
        text = (
            "The court held that the petitioner's appeal under Section 302 "
            "of the Indian Penal Code is dismissed. The learned counsel for "
            "the respondent argued that the judgment of the tribunal was "
            "correct. The bench consisting of three judges considered the "
            "writ petition filed under Article 226 of the Constitution. "
        ) * 10  # > 2000 chars
        result = score_text_quality(text)
        assert result.tier == "high"
        assert result.char_count > 2000
        assert result.legal_keyword_count >= 3

    def test_medium_tier_moderate_text(self):
        """Text 500-2000 chars with 1-2 legal keywords should score 'medium'."""
        text = (
            "The court considered the matter carefully. "
            "Various arguments were presented by both sides. "
            "The facts of the case are straightforward. "
        ) * 5  # ~500-600 chars, has "court" keyword
        result = score_text_quality(text)
        assert result.tier == "medium"
        assert result.char_count > 500
        assert result.legal_keyword_count >= 1

    def test_low_tier_short_text(self):
        """Very short text without legal keywords should score 'low'."""
        text = "Hello world."
        result = score_text_quality(text)
        assert result.tier == "low"
        assert result.char_count < 500

    def test_low_tier_empty_text(self):
        """Empty text should score 'low' without errors."""
        result = score_text_quality("")
        assert result.tier == "low"
        assert result.char_count == 0
        assert result.legal_keyword_count == 0

    def test_low_alpha_ratio_forces_low_tier(self):
        """OCR garbage with <40% alphabetic chars should be forced to 'low'."""
        # Build text with many legal keywords but terrible alpha ratio
        garbage = "!@#$%^&*(){}|><??/// 12345 [][] ~~~~ " * 100
        # Add just enough legal words to otherwise qualify as high
        text = garbage + " court petitioner respondent section act judgment order "
        result = score_text_quality(text)
        assert result.tier == "low", "Low alpha ratio should force tier to 'low'"

    def test_low_chars_per_page_forces_low_tier(self):
        """Sparse text with known page count should be forced to 'low'."""
        text = (
            "The court held that the petitioner's appeal is dismissed. "
            "The learned counsel argued various points. The bench considered all. "
        ) * 10  # ~600 chars total, legal enough for 'medium'
        # But if spread across 100 pages, chars/page < 100 → low
        result = score_text_quality(text, page_count=100)
        assert result.tier == "low", "Sparse text across many pages should be 'low'"

    def test_chars_per_page_not_checked_when_zero_pages(self):
        """When page_count=0, chars-per-page check should be skipped."""
        text = ("The court held that the petition under Section 302 is dismissed. ") * 10
        result = score_text_quality(text, page_count=0)
        assert result.tier in ("high", "medium")

    def test_ocr_used_flag_recorded(self):
        """The ocr_used flag should be faithfully recorded."""
        result_no_ocr = score_text_quality("court order", ocr_used=False)
        result_ocr = score_text_quality("court order", ocr_used=True)
        assert result_no_ocr.ocr_used is False
        assert result_ocr.ocr_used is True

    def test_page_count_recorded(self):
        """The page_count should be faithfully recorded."""
        result = score_text_quality("court text", page_count=42)
        assert result.page_count == 42

    def test_returns_text_quality_dataclass(self):
        """Return value should be a TextQuality instance."""
        result = score_text_quality("Some text")
        assert isinstance(result, TextQuality)
        assert hasattr(result, "text")
        assert hasattr(result, "tier")
        assert hasattr(result, "char_count")
        assert hasattr(result, "legal_keyword_count")

    def test_keyword_counting(self):
        """Legal keywords should be counted correctly."""
        text = "The court and the petitioner and the respondent appeared before the bench."
        result = score_text_quality(text)
        # court, petitioner, respondent, bench → at least 4
        assert result.legal_keyword_count >= 4


class TestExtractAndScore:
    """G2: Tests for extract_and_score() async function."""

    @pytest.mark.asyncio
    async def test_extract_and_score_returns_text_quality(self):
        """extract_and_score should return a TextQuality instance."""
        long_legal_text = (
            "The court held that the petitioner's appeal under Section 302 "
            "of the Indian Penal Code is dismissed. The learned counsel argued. "
        ) * 20

        with patch(
            "app.core.ingestion.pdf.extract_pdf_text",
            new_callable=AsyncMock,
            return_value=(long_legal_text, 10, []),
        ):
            result = await extract_and_score("/fake/path.pdf")

        assert isinstance(result, TextQuality)
        assert result.tier == "high"
        assert result.ocr_used is False
        assert result.page_count == 10

    @pytest.mark.asyncio
    async def test_extract_and_score_falls_back_to_ocr(self):
        """When pdfplumber returns < 100 chars, should fall back to OCR."""
        ocr_text = (
            "The court held that the petitioner's appeal is dismissed. "
            "The learned counsel for the respondent argued. "
        ) * 20

        with (
            patch(
                "app.core.ingestion.pdf.extract_pdf_text",
                new_callable=AsyncMock,
                return_value=("short", 5, []),  # < 100 chars triggers OCR
            ),
            patch(
                "app.core.ingestion.pdf.extract_with_ocr",
                new_callable=AsyncMock,
                return_value=(ocr_text, False, 5),
            ),
        ):
            result = await extract_and_score("/fake/path.pdf")

        assert result.ocr_used is True
        assert result.char_count > 100

    @pytest.mark.asyncio
    async def test_extract_and_score_empty_extraction(self):
        """When both pdfplumber and OCR fail, should return empty with 'low' tier."""
        with (
            patch(
                "app.core.ingestion.pdf.extract_pdf_text",
                new_callable=AsyncMock,
                return_value=("", 0, []),
            ),
            patch(
                "app.core.ingestion.pdf.extract_with_ocr",
                new_callable=AsyncMock,
                return_value=("", False, 0),
            ),
        ):
            result = await extract_and_score("/fake/path.pdf")

        assert result.tier == "low"
        assert result.char_count == 0
        assert result.ocr_used is True

    @pytest.mark.asyncio
    async def test_extract_and_score_sufficient_pdfplumber_text(self):
        """When pdfplumber returns >= 100 chars, OCR should not be invoked."""
        sufficient_text = (
            "The court held that the petitioner's appeal under Section 302 "
            "of the Indian Penal Code is dismissed. "
        )

        with (
            patch(
                "app.core.ingestion.pdf.extract_pdf_text",
                new_callable=AsyncMock,
                return_value=(sufficient_text, 1, []),
            ) as mock_pdf,
            patch(
                "app.core.ingestion.pdf.extract_with_ocr",
                new_callable=AsyncMock,
            ) as mock_ocr,
        ):
            result = await extract_and_score("/fake/path.pdf")

        mock_pdf.assert_called_once()
        mock_ocr.assert_not_called()
        assert result.ocr_used is False
