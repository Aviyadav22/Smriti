"""Unit tests for PDF text extraction, cleaning, and quality assessment.

Tests Phase 1A changes: text cleaning (ligatures, zero-width chars, page numbers,
repeated headers, whitespace normalization), smart page joining, extraction quality
assessment, and async interface verification.
"""

import asyncio
import inspect

import pytest

from app.core.ingestion.pdf import (
    _smart_page_join,
    assess_extraction_quality,
    clean_extracted_text,
    extract_pdf_text,
)


class TestCleanExtractedTextLigatures:
    """Tests for Unicode ligature decomposition via NFKC normalization."""

    def test_clean_extracted_text_removes_ligatures(self):
        """Ligature codepoints U+FB00 (ff), U+FB01 (fi), U+FB02 (fl) should
        be decomposed to their ASCII equivalents."""
        text = "e\ufb00ective o\ufb03ce a\ufb02utter"
        result = clean_extracted_text(text)
        assert "ff" in result, "ff ligature (U+FB00) not decomposed"
        assert "ffi" in result or "fi" in result, "ffi/fi ligature not decomposed"
        assert "fl" in result, "fl ligature (U+FB02) not decomposed"
        # Original ligature codepoints must be gone
        assert "\ufb00" not in result
        assert "\ufb01" not in result
        assert "\ufb02" not in result
        assert "\ufb03" not in result


class TestCleanExtractedTextZeroWidth:
    """Tests for zero-width and invisible character removal."""

    def test_clean_extracted_text_removes_zero_width_chars(self):
        """Zero-width space, ZWNJ, ZWJ, BOM, and soft hyphen must all be removed."""
        text = "Hello\u200B \u200CWorld\u200D foo\uFEFF bar\u00AD baz"
        result = clean_extracted_text(text)
        assert "\u200B" not in result, "Zero-width space not removed"
        assert "\u200C" not in result, "ZWNJ not removed"
        assert "\u200D" not in result, "ZWJ not removed"
        assert "\uFEFF" not in result, "BOM not removed"
        assert "\u00AD" not in result, "Soft hyphen not removed"
        # Actual words must be preserved
        assert "Hello" in result
        assert "World" in result
        assert "baz" in result


class TestCleanExtractedTextPageNumbers:
    """Tests for standalone page number removal."""

    def test_clean_extracted_text_removes_page_numbers(self):
        """Standalone line page numbers like '5', ' 23 ', '-12-' should be removed,
        but inline references like 'Section 302' must survive."""
        text = (
            "Some legal text here.\n"
            "5\n"
            " 23 \n"
            "-12-\n"
            "Section 302 of the Indian Penal Code\n"
            "The court observed in paragraph 42 that\n"
        )
        result = clean_extracted_text(text)
        # Standalone page numbers removed
        assert "\n5\n" not in result
        assert "\n 23 \n" not in result
        assert "\n-12-\n" not in result
        # Inline legal references preserved
        assert "Section 302" in result
        assert "paragraph 42" in result


class TestCleanExtractedTextRepeatedHeaders:
    """Tests for repeated header/footer deduplication."""

    def test_clean_extracted_text_removes_repeated_headers(self):
        """If the same header appears on 3+ pages, only the first occurrence
        should be kept."""
        # Simulate 5 page-like segments separated by triple newlines
        page_content = "Some unique content on this page about the case."
        pages = []
        for i in range(5):
            pages.append(
                "SUPREME COURT OF INDIA\n"
                "CIVIL APPELLATE JURISDICTION\n"
                f"Page {i + 1} content: {page_content}"
            )
        text = "\n\n\n".join(pages)
        result = clean_extracted_text(text)

        # The header text should appear only once (first occurrence kept)
        assert result.count("SUPREME COURT OF INDIA") == 1
        assert result.count("CIVIL APPELLATE JURISDICTION") == 1
        # But page-unique content should be preserved for all pages
        assert result.count("content:") == 5


class TestCleanExtractedTextWhitespace:
    """Tests for whitespace normalization."""

    def test_clean_extracted_text_normalizes_whitespace(self):
        """Three or more consecutive newlines should be collapsed to exactly two."""
        text = "First paragraph.\n\n\n\n\nSecond paragraph.\n\n\n\n\n\nThird paragraph."
        result = clean_extracted_text(text)
        # No runs of 3+ newlines should remain
        assert "\n\n\n" not in result
        # But double newlines (paragraph breaks) should be preserved
        assert "\n\n" in result
        assert "First paragraph." in result
        assert "Third paragraph." in result


class TestCleanExtractedTextPreservesLegalContent:
    """Tests that legal substance is not damaged by cleaning."""

    def test_clean_extracted_text_preserves_legal_content(self):
        """Legal text with section references, case citations, and proper
        paragraphs must pass through cleaning intact."""
        text = (
            "Section 302 of the Indian Penal Code, 1860 prescribes punishment "
            "for murder. The Hon'ble Supreme Court in (2020) 3 SCC 145 held "
            "that the burden of proof lies on the prosecution.\n\n"
            "Article 21 of the Constitution guarantees the right to life and "
            "personal liberty. This fundamental right cannot be curtailed "
            "except according to procedure established by law."
        )
        result = clean_extracted_text(text)
        assert "Section 302 of the Indian Penal Code, 1860" in result
        assert "(2020) 3 SCC 145" in result
        assert "Article 21" in result
        assert "procedure established by law" in result


class TestSmartPageJoin:
    """Tests for _smart_page_join() paragraph continuity detection."""

    def test_smart_page_join_continues_paragraph(self):
        """When page 1 ends without terminal punctuation and page 2 starts
        with a lowercase letter, they should be joined with a single space."""
        pages = [
            "the appellant argued that",
            "the evidence was insufficient",
        ]
        result = _smart_page_join(pages)
        # Should be joined with a space, not a paragraph break
        assert "that the evidence" in result
        assert "that\n\nthe evidence" not in result

    def test_smart_page_join_respects_paragraph_break(self):
        """When page 1 ends with terminal punctuation and page 2 starts with
        an uppercase letter, a paragraph break should be inserted."""
        pages = [
            "The first issue was dismissed.",
            "The next issue concerns jurisdiction.",
        ]
        result = _smart_page_join(pages)
        # Should be separated by double newline
        assert "dismissed.\n\nThe next issue" in result

    def test_smart_page_join_single_page(self):
        """A single page should be returned as-is."""
        pages = ["Only one page of content here."]
        result = _smart_page_join(pages)
        assert result == "Only one page of content here."

    def test_smart_page_join_empty_list(self):
        """Empty page list should return empty string."""
        assert _smart_page_join([]) == ""


class TestAssessExtractionQuality:
    """Tests for assess_extraction_quality()."""

    def test_assess_extraction_quality_good(self):
        """Text with high alpha ratio and legal markers should be rated 'good'."""
        text = (
            "The appellant filed a Civil Appeal under Section 302 of the Indian "
            "Penal Code. The learned Judge of the High Court observed that the "
            "respondent had failed to establish the claim. The evidence on record "
            "clearly indicates that the Article 21 rights were not violated."
        )
        quality = assess_extraction_quality(text)
        assert quality["quality"] == "good"
        assert quality["alpha_ratio"] > 0.6
        assert quality["has_legal_markers"] is True

    def test_assess_extraction_quality_poor(self):
        """Garbled OCR text with low alpha ratio should be rated 'poor'."""
        text = "!@#$%^&*(){}|><??/// 12345 [][] ~~~~ %%%% #### $$$$$ ++++ ===="
        quality = assess_extraction_quality(text)
        assert quality["quality"] == "poor"
        assert quality["alpha_ratio"] < 0.5
        assert quality["has_legal_markers"] is False

    def test_assess_extraction_quality_returns_char_count(self):
        """The result should include an accurate character count."""
        text = "Hello world"
        quality = assess_extraction_quality(text)
        assert quality["char_count"] == len(text)

    def test_assess_extraction_quality_empty_text(self):
        """Empty text should be rated 'poor' without errors."""
        quality = assess_extraction_quality("")
        assert quality["quality"] == "poor"
        assert quality["char_count"] == 0


class TestExtractPdfTextAsync:
    """Tests verifying that extract_pdf_text is properly async."""

    def test_extract_pdf_text_is_async(self):
        """extract_pdf_text must be a coroutine function (async def)."""
        assert asyncio.iscoroutinefunction(extract_pdf_text), (
            "extract_pdf_text should be an async function"
        )

    def test_extract_pdf_text_returns_coroutine(self):
        """Calling extract_pdf_text should return a coroutine object."""
        result = extract_pdf_text("/nonexistent/path.pdf")
        assert inspect.iscoroutine(result), (
            "extract_pdf_text() should return a coroutine"
        )
        # Clean up the coroutine to avoid RuntimeWarning
        result.close()
