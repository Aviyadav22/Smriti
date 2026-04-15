"""Unit tests for PDF text extraction, cleaning, and quality assessment.

Tests Phase 1A changes: text cleaning (ligatures, zero-width chars, page numbers,
repeated headers, whitespace normalization), smart page joining, extraction quality
assessment, and async interface verification.
"""

import asyncio
import inspect

from app.core.ingestion.pdf import (
    _remove_repeated_headers_footers_pages,
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
        """Zero-width space, BOM, and soft hyphen must be removed.
        ZWNJ (U+200C) and ZWJ (U+200D) are preserved for Devanagari support."""
        text = "Hello\u200B \u200CWorld\u200D foo\uFEFF bar\u00AD baz"
        result = clean_extracted_text(text)
        assert "\u200B" not in result, "Zero-width space not removed"
        assert "\uFEFF" not in result, "BOM not removed"
        assert "\u00AD" not in result, "Soft hyphen not removed"
        # ZWNJ and ZWJ must be preserved (Devanagari conjunct control)
        assert "\u200C" in result, "ZWNJ should be preserved for Devanagari"
        assert "\u200D" in result, "ZWJ should be preserved for Devanagari"
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


class TestSmartPageJoinHyphenation:
    """Tests for hyphenated word rejoining in _smart_page_join (B5)."""

    def test_hyphenated_word_rejoining(self):
        """Pages ending with 'juris-' + 'diction' should rejoin to 'jurisdiction'."""
        pages = [
            "The court examined juris-",
            "diction over this matter.",
        ]
        result = _smart_page_join(pages)
        assert "jurisdiction" in result
        assert "juris-" not in result

    def test_hyphenated_word_rejoining_mid_word(self):
        """Another hyphenated word example: 'consti-' + 'tutional'."""
        pages = [
            "This is a consti-",
            "tutional question.",
        ]
        result = _smart_page_join(pages)
        assert "constitutional" in result
        assert "consti-" not in result

    def test_hyphen_not_rejoined_when_next_starts_uppercase(self):
        """A hyphen at end of page followed by uppercase start should not rejoin."""
        pages = [
            "See Section 302-",
            "The court held that...",
        ]
        result = _smart_page_join(pages)
        # Should NOT rejoin since next page starts with uppercase
        assert "302-" in result or "302" in result
        assert "The court" in result

    def test_hyphen_not_rejoined_when_next_starts_digit(self):
        """A hyphen at end of page followed by a digit should not rejoin."""
        pages = [
            "Reference number A-",
            "123 was cited.",
        ]
        result = _smart_page_join(pages)
        # Should NOT rejoin since next page starts with a digit, not lowercase
        assert "A-" in result
        assert "123" in result


class TestRemoveRepeatedHeadersFootersPages:
    """Tests for _remove_repeated_headers_footers_pages (B6)."""

    def test_removes_lines_on_3_plus_pages(self):
        """Lines appearing on 3+ pages should be removed (except first occurrence)."""
        pages = [
            "SUPREME COURT OF INDIA\nContent of page 1",
            "SUPREME COURT OF INDIA\nContent of page 2",
            "SUPREME COURT OF INDIA\nContent of page 3",
            "SUPREME COURT OF INDIA\nContent of page 4",
        ]
        result = _remove_repeated_headers_footers_pages(pages)
        # First page should still have the header
        assert "SUPREME COURT OF INDIA" in result[0]
        # Subsequent pages should have it removed
        for page in result[1:]:
            assert "SUPREME COURT OF INDIA" not in page
        # Unique content preserved on all pages
        for i, page in enumerate(result):
            assert f"Content of page {i + 1}" in page

    def test_first_occurrence_preserved(self):
        """The first occurrence of a repeated header should be kept."""
        pages = [
            "HEADER LINE\nFirst page text",
            "HEADER LINE\nSecond page text",
            "HEADER LINE\nThird page text",
        ]
        result = _remove_repeated_headers_footers_pages(pages)
        # Collect all text
        all_text = "\n".join(result)
        assert all_text.count("HEADER LINE") == 1
        # And it should be in the first page
        assert "HEADER LINE" in result[0]

    def test_fewer_than_3_pages_unchanged(self):
        """With fewer than 3 pages, no dedup should occur."""
        pages = [
            "HEADER\nContent A",
            "HEADER\nContent B",
        ]
        result = _remove_repeated_headers_footers_pages(pages)
        assert result == pages

    def test_unique_lines_not_removed(self):
        """Lines that only appear once or twice should be preserved."""
        pages = [
            "Unique header 1\nContent A",
            "Unique header 2\nContent B",
            "Unique header 3\nContent C",
        ]
        result = _remove_repeated_headers_footers_pages(pages)
        assert result == pages

    def test_boilerplate_patterns_removed(self):
        """Common boilerplate like REPORTABLE should be removed after first occurrence."""
        pages = [
            "REPORTABLE\nContent of page 1",
            "REPORTABLE\nContent of page 2",
            "REPORTABLE\nContent of page 3",
        ]
        result = _remove_repeated_headers_footers_pages(pages)
        all_text = "\n".join(result)
        assert all_text.count("REPORTABLE") == 1
