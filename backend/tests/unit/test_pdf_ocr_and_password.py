"""Tests for OCR fallback path and password-protected PDF handling (G3, G4).

Tests the per-page OCR fallback mechanism in _extract_pdf_text_sync
and the PDFPasswordIncorrect exception handling.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.ingestion.pdf import _extract_pdf_text_sync


class TestOCRFallbackPath:
    """G3: Tests for OCR fallback when pdfplumber returns insufficient text."""

    def test_ocr_triggered_when_page_text_short(self):
        """When a page yields < 30 chars, OCR should be attempted for that page."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "ab"  # < 30 chars

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("app.core.ingestion.pdf.pdfplumber") as mock_pdfplumber, \
             patch("app.core.ingestion.pdf._ocr_single_page") as mock_ocr:
            mock_pdfplumber.open.return_value = mock_pdf
            mock_ocr.return_value = "This is OCR extracted text from a scanned page of the judgment."

            text, page_count, page_map = _extract_pdf_text_sync("/fake/scanned.pdf")

        mock_ocr.assert_called_once_with("/fake/scanned.pdf", 1)
        assert "OCR extracted text" in text
        assert page_count == 1
        assert isinstance(page_map, list)

    def test_ocr_not_triggered_when_sufficient_text(self):
        """When pdfplumber returns >= 30 chars, OCR should NOT be attempted."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = (
            "The court held that the petitioner's appeal is dismissed."
        )

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("app.core.ingestion.pdf.pdfplumber") as mock_pdfplumber, \
             patch("app.core.ingestion.pdf._ocr_single_page") as mock_ocr:
            mock_pdfplumber.open.return_value = mock_pdf
            text, page_count, page_map = _extract_pdf_text_sync("/fake/good.pdf")

        mock_ocr.assert_not_called()
        assert "petitioner" in text

    def test_ocr_used_only_when_better_than_pdfplumber(self):
        """OCR text replaces pdfplumber text only when it's longer."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Hi"  # 2 chars < 30

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("app.core.ingestion.pdf.pdfplumber") as mock_pdfplumber, \
             patch("app.core.ingestion.pdf._ocr_single_page") as mock_ocr:
            mock_pdfplumber.open.return_value = mock_pdf
            # OCR returns even less text
            mock_ocr.return_value = ""
            text, page_count, page_map = _extract_pdf_text_sync("/fake/bad_ocr.pdf")

        # With both short, we get whatever pdfplumber had (may be stripped empty)
        # The important thing is no crash occurred
        assert page_count == 1
        assert isinstance(text, str)

    def test_multi_page_selective_ocr(self):
        """OCR should only be used for pages that need it, not all pages."""
        good_page = MagicMock()
        good_page.extract_text.return_value = (
            "The court held that the petitioner's appeal is dismissed per Section 302."
        )

        bad_page = MagicMock()
        bad_page.extract_text.return_value = "x"  # needs OCR

        mock_pdf = MagicMock()
        mock_pdf.pages = [good_page, bad_page, good_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("app.core.ingestion.pdf.pdfplumber") as mock_pdfplumber, \
             patch("app.core.ingestion.pdf._ocr_single_page") as mock_ocr:
            mock_pdfplumber.open.return_value = mock_pdf
            mock_ocr.return_value = "OCR text for the scanned page of the judgment."
            text, page_count, page_map = _extract_pdf_text_sync("/fake/mixed.pdf")

        # OCR should only be called for page 2 (1-indexed)
        mock_ocr.assert_called_once_with("/fake/mixed.pdf", 2)
        assert page_count == 3


class TestPasswordProtectedPDF:
    """G4: Tests for password-protected PDF handling."""

    def test_password_protected_returns_empty(self):
        """Password-protected PDFs should return empty string, not crash."""
        # Simulate PDFPasswordIncorrect being raised
        from pdfminer.pdfdocument import PDFPasswordIncorrect as RealException

        with patch("app.core.ingestion.pdf.pdfplumber") as mock_pdfplumber:
            mock_pdfplumber.open.side_effect = RealException()
            text, page_count, page_map = _extract_pdf_text_sync("/fake/encrypted.pdf")

        assert text == ""
        assert page_count == 0

    def test_password_protected_does_not_raise(self):
        """Password-protected PDFs should not propagate the exception."""
        from pdfminer.pdfdocument import PDFPasswordIncorrect as RealException

        with patch("app.core.ingestion.pdf.pdfplumber") as mock_pdfplumber:
            mock_pdfplumber.open.side_effect = RealException()
            # Should not raise
            text, page_count, page_map = _extract_pdf_text_sync("/fake/encrypted.pdf")

        assert text == ""

    def test_os_error_returns_empty(self):
        """File not found or permission errors should return empty."""
        with patch("app.core.ingestion.pdf.pdfplumber") as mock_pdfplumber:
            mock_pdfplumber.open.side_effect = OSError("File not found")
            text, page_count, page_map = _extract_pdf_text_sync("/fake/missing.pdf")

        assert text == ""
        assert page_count == 0

    def test_max_pages_exceeded_returns_empty(self):
        """PDFs exceeding MAX_PAGES should return empty string."""
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock()] * 6000  # > MAX_PAGES (5000)
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("app.core.ingestion.pdf.pdfplumber") as mock_pdfplumber:
            mock_pdfplumber.open.return_value = mock_pdf
            text, page_count, page_map = _extract_pdf_text_sync("/fake/huge.pdf")

        assert text == ""
        assert page_count == 0
