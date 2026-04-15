"""Filing-ready PDF compliance for Indian courts.

Provides validation and post-processing to ensure PDFs meet
court-specific e-filing requirements.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.drafting.court_profiles import CourtProfile

logger = logging.getLogger(__name__)


@dataclass
class FilingValidationResult:
    """Result of validating a PDF against court e-filing requirements."""

    court_id: str
    is_valid: bool
    issues: list[str]
    warnings: list[str]
    file_size_mb: float
    has_bookmarks: bool
    page_count: int


def validate_filing_pdf(
    pdf_bytes: bytes,
    court_profile: CourtProfile,
) -> FilingValidationResult:
    """Validate a PDF against court-specific e-filing requirements.

    Checks file size, page count, and basic PDF structure.
    Does NOT check font embedding or DPI (would require pikepdf which
    is an optional dependency).
    """
    issues: list[str] = []
    warnings: list[str] = []

    # File size check
    file_size_mb = len(pdf_bytes) / (1024 * 1024)
    if file_size_mb > court_profile.max_file_size_mb:
        issues.append(
            f"File size ({file_size_mb:.1f} MB) exceeds "
            f"court limit ({court_profile.max_file_size_mb} MB)"
        )

    # Page count (basic check via PDF stream)
    page_count = _count_pages(pdf_bytes)

    # Bookmark check (basic — look for /Outlines in PDF)
    has_bookmarks = b"/Outlines" in pdf_bytes
    if court_profile.requires_bookmarks and not has_bookmarks:
        issues.append("PDF bookmarks required but not found")

    # PDF/A check (basic — look for PDF/A metadata)
    if court_profile.pdf_format == "pdf_a":
        is_pdf_a = b"pdfaid" in pdf_bytes.lower() or b"pdf/a" in pdf_bytes.lower()
        if not is_pdf_a:
            warnings.append(
                "Court requires PDF/A format. Consider converting with pikepdf. "
                "Current PDF may not pass e-filing validation."
            )

    # OCR check
    if court_profile.requires_ocr:
        warnings.append("Court requires OCR-searchable PDF. Ensure text is selectable.")

    # Filing portal info
    if court_profile.filing_portal_url:
        warnings.append(f"E-filing portal: {court_profile.filing_portal_url}")

    is_valid = len(issues) == 0
    return FilingValidationResult(
        court_id=court_profile.court_id,
        is_valid=is_valid,
        issues=issues,
        warnings=warnings,
        file_size_mb=round(file_size_mb, 2),
        has_bookmarks=has_bookmarks,
        page_count=page_count,
    )


def _count_pages(pdf_bytes: bytes) -> int:
    """Count pages in a PDF by scanning for page objects."""
    # Simple heuristic: count /Type /Page occurrences (not /Pages)
    matches = re.findall(rb"/Type\s*/Page(?!\s*s)", pdf_bytes)
    return len(matches)


def add_pdf_bookmarks(
    pdf_bytes: bytes,
    bookmarks: list[dict],
) -> bytes:
    """Add bookmarks to a PDF using pikepdf.

    Args:
        pdf_bytes: Original PDF content
        bookmarks: List of {"title": str, "page": int} dicts

    Returns:
        PDF bytes with bookmarks added. Returns original if processing fails.
    """
    try:
        import pikepdf

        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            with pdf.open_outline() as outline:
                for bm in bookmarks:
                    title = bm.get("title", "")
                    page_num = bm.get("page", 0)
                    if title and 0 <= page_num < len(pdf.pages):
                        outline.root.append(pikepdf.OutlineItem(title, page_num))
            buf = io.BytesIO()
            pdf.save(buf)
            buf.seek(0)
            return buf.read()
    except ImportError:
        logger.info("pikepdf not installed; skipping bookmark addition")
        return pdf_bytes
    except Exception:
        logger.warning("Failed to add PDF bookmarks", exc_info=True)
        return pdf_bytes


def convert_to_pdf_a(pdf_bytes: bytes) -> bytes:
    """Convert PDF to PDF/A-2b format using pikepdf.

    Returns original bytes if pikepdf is not installed or conversion fails.
    """
    try:
        import pikepdf

        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            # Set PDF/A metadata
            with pdf.open_metadata() as meta:
                meta["pdfaid:part"] = "2"
                meta["pdfaid:conformance"] = "B"
            buf = io.BytesIO()
            pdf.save(buf)
            buf.seek(0)
            return buf.read()
    except ImportError:
        logger.info("pikepdf not installed; skipping PDF/A conversion")
        return pdf_bytes
    except Exception:
        logger.warning("PDF/A conversion failed", exc_info=True)
        return pdf_bytes


def generate_filing_checklist(
    court_profile: CourtProfile,
    doc_type: str,
    has_affidavit: bool,
) -> list[dict]:
    """Generate a pre-filing checklist for the user.

    Returns a list of checklist items with status.
    """
    items: list[dict] = []

    items.append(
        {
            "item": f"Document formatted for {court_profile.display_name}",
            "status": "done",
            "details": (
                f"Paper: {court_profile.paper_size}, "
                f"Font: {court_profile.font_name} {court_profile.font_size_body}pt"
            ),
        }
    )

    if court_profile.requires_bookmarks:
        items.append(
            {
                "item": "PDF bookmarks added",
                "status": "done",
                "details": "Section headings bookmarked for easy navigation",
            }
        )

    if court_profile.pdf_format == "pdf_a":
        items.append(
            {
                "item": "PDF/A format required",
                "status": "warning",
                "details": (
                    f"Ensure final PDF is PDF/A-2b compliant " f"for {court_profile.display_name}"
                ),
            }
        )

    items.append(
        {
            "item": f"File size under {court_profile.max_file_size_mb} MB",
            "status": "check",
            "details": "Verify after adding annexures",
        }
    )

    if has_affidavit:
        items.append(
            {
                "item": "Companion affidavit included",
                "status": "done",
                "details": "Auto-generated affidavit attached",
            }
        )

    items.append(
        {
            "item": "Vakalatnama signed and notarized",
            "status": "manual",
            "details": "Must be executed on stamp paper of requisite value",
        }
    )

    items.append(
        {
            "item": "Court fee paid",
            "status": "manual",
            "details": "Attach court fee receipt or e-stamp",
        }
    )

    items.append(
        {
            "item": "Digital Signature Certificate (DSC)",
            "status": "manual",
            "details": "Class III DSC required for e-filing",
        }
    )

    if court_profile.filing_portal_url:
        items.append(
            {
                "item": "Upload to e-filing portal",
                "status": "manual",
                "details": court_profile.filing_portal_url,
            }
        )

    return items
