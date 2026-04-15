"""Tests for editorial content filters in PDF text cleaning."""

import pytest

from app.core.ingestion.pdf import (
    _EDITORIAL_RE,
    _REPORTER_PAGE_MARKER_RE,
    clean_extracted_text,
)


class TestEditorialRegex:
    """Verify editorial metadata patterns match expected strings."""

    @pytest.mark.parametrize(
        "line",
        [
            "†Headnotes prepared by: Ankit Gyan",
            "  Headnotes prepared by: Ankit Gyan  ",
            "Headnote prepared by: Some Name",
            "† Headnotes prepared by: A.B. Sharma",
            "Result of the case: Appeals allowed.",
            "  Result of the case: Petition dismissed.  ",
            "Prepared by: Legal Editor",
            "Formatted by: SCR Editorial Team",
            "Compiled by: Reporter Staff",
            "Digest: Constitutional law — Article 21",
            "Catchwords",
            "Catchword:",
            "Cases Referred:",
            "Cases Referred",
            "Cases Cited:",
            "Legislation Cited:",
        ],
    )
    def test_editorial_re_matches(self, line: str):
        assert _EDITORIAL_RE.search(line), f"Should match: {line!r}"

    @pytest.mark.parametrize(
        "line",
        [
            "The court held that the appeal is allowed.",
            "The petitioner prepared the documents.",
            "Headnotes are an important part of legal reporting.",
            "61. In the aforesaid context, it would be apposite",
        ],
    )
    def test_editorial_re_does_not_match_judgment_text(self, line: str):
        assert not _EDITORIAL_RE.search(line), f"Should NOT match: {line!r}"


class TestReporterPageMarkerRegex:
    """Verify SCR page marker patterns match expected strings."""

    @pytest.mark.parametrize(
        "line",
        [
            "[2026] 1 S.C.R. 63",
            "[2026] 1 S.C.R. 30",
            "64 [2026] 1 S.C.R.",
            "65 [2026] 1 S.C.R.",
            "2026 1 SCR 63",
        ],
    )
    def test_reporter_page_marker_matches(self, line: str):
        assert _REPORTER_PAGE_MARKER_RE.search(line), f"Should match: {line!r}"

    @pytest.mark.parametrize(
        "line",
        [
            "reported in (2018) 12 SCC 471",
            "[2026] 1 S.C.R. 30 some text continues here",
            "Section 302 of the IPC",
        ],
    )
    def test_reporter_page_marker_no_false_positives(self, line: str):
        assert not _REPORTER_PAGE_MARKER_RE.search(line), f"Should NOT match: {line!r}"


class TestCleanExtractedTextEditorial:
    """Verify clean_extracted_text strips editorial content."""

    def test_strips_headnotes_byline(self):
        text = "Some judgment text.\n†Headnotes prepared by: Ankit Gyan\n\nMore text."
        result = clean_extracted_text(text)
        assert "Ankit Gyan" not in result
        assert "judgment text" in result
        assert "More text" in result

    def test_strips_result_of_case(self):
        text = "The appeal is allowed.\nResult of the case: Appeals allowed.\n"
        result = clean_extracted_text(text)
        assert "Result of the case" not in result
        assert "appeal is allowed" in result

    def test_strips_scr_page_markers(self):
        text = "Some text\n[2026] 1 S.C.R. 63\nMore text after marker."
        result = clean_extracted_text(text)
        assert "S.C.R. 63" not in result
        assert "Some text" in result
        assert "More text after marker" in result

    def test_preserves_normal_judgment_text(self):
        text = (
            "61. In the aforesaid context, it would be apposite to briefly explain "
            "what constitutes as de jure ineligibility under Section 12(5)."
        )
        result = clean_extracted_text(text)
        assert "de jure ineligibility" in result
        assert "Section 12(5)" in result


class TestPromptEditorialExclusion:
    """Verify prompts contain editorial exclusion instructions."""

    def test_headnotes_rule_excludes_editorial(self):
        from app.core.legal.prompts import METADATA_EXTRACTION_SYSTEM

        assert "Headnotes prepared by" in METADATA_EXTRACTION_SYSTEM

    def test_operative_order_excludes_editorial(self):
        from app.core.legal.prompts import METADATA_EXTRACTION_SYSTEM

        assert "Result of the case:" in METADATA_EXTRACTION_SYSTEM

    def test_rule_30_editorial_content(self):
        from app.core.legal.prompts import METADATA_EXTRACTION_SYSTEM

        assert "EDITORIAL CONTENT" in METADATA_EXTRACTION_SYSTEM
        assert "reporter-added content" in METADATA_EXTRACTION_SYSTEM
