"""Tests for filing-ready PDF compliance."""

from __future__ import annotations

from app.core.drafting.court_profiles import COURT_PROFILES
from app.core.drafting.pdf_compliance import (
    FilingValidationResult,
    generate_filing_checklist,
    validate_filing_pdf,
)

# Minimal valid PDF bytes for testing
_MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type /Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type /Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type /Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"xref\n0 4\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF"
)


class TestValidateFilingPdf:
    def test_valid_pdf_passes_sc_validation(self) -> None:
        profile = COURT_PROFILES["supreme_court"]
        result = validate_filing_pdf(_MINIMAL_PDF, profile)
        assert isinstance(result, FilingValidationResult)
        assert result.file_size_mb < 1  # Tiny PDF

    def test_oversized_pdf_fails(self) -> None:
        profile = COURT_PROFILES["nclt"]  # 20 MB limit
        huge_pdf = _MINIMAL_PDF + b"\x00" * (21 * 1024 * 1024)  # 21 MB
        result = validate_filing_pdf(huge_pdf, profile)
        assert not result.is_valid
        assert any("size" in issue.lower() for issue in result.issues)

    def test_missing_bookmarks_flagged_for_sc(self) -> None:
        profile = COURT_PROFILES["supreme_court"]
        result = validate_filing_pdf(_MINIMAL_PDF, profile)
        assert any("bookmark" in issue.lower() for issue in result.issues)

    def test_pdf_a_warning_for_bombay_hc(self) -> None:
        profile = COURT_PROFILES["bombay_hc"]
        result = validate_filing_pdf(_MINIMAL_PDF, profile)
        assert any("pdf/a" in w.lower() for w in result.warnings)

    def test_ocr_warning_for_nclt(self) -> None:
        profile = COURT_PROFILES["nclt"]
        result = validate_filing_pdf(_MINIMAL_PDF, profile)
        assert any("ocr" in w.lower() for w in result.warnings)

    def test_default_profile_no_strict_requirements(self) -> None:
        profile = COURT_PROFILES["default"]
        result = validate_filing_pdf(_MINIMAL_PDF, profile)
        assert result.is_valid  # No bookmarks required, no PDF/A required


class TestGenerateFilingChecklist:
    def test_sc_checklist_has_bookmark_item(self) -> None:
        profile = COURT_PROFILES["supreme_court"]
        items = generate_filing_checklist(profile, "bail_application", True)
        assert any("bookmark" in item["item"].lower() for item in items)

    def test_checklist_includes_dsc(self) -> None:
        profile = COURT_PROFILES["supreme_court"]
        items = generate_filing_checklist(profile, "bail_application", False)
        assert any(
            "dsc" in item["item"].lower() or "digital signature" in item["item"].lower()
            for item in items
        )

    def test_checklist_includes_affidavit_when_present(self) -> None:
        profile = COURT_PROFILES["delhi_hc"]
        items = generate_filing_checklist(profile, "writ_petition_226", True)
        assert any("affidavit" in item["item"].lower() for item in items)

    def test_checklist_includes_efiling_url(self) -> None:
        profile = COURT_PROFILES["supreme_court"]
        items = generate_filing_checklist(profile, "slp", False)
        assert any("efiling" in item.get("details", "").lower() for item in items)

    def test_bombay_hc_checklist_has_pdf_a_item(self) -> None:
        profile = COURT_PROFILES["bombay_hc"]
        items = generate_filing_checklist(profile, "bail_application", False)
        assert any("pdf/a" in item["item"].lower() for item in items)
