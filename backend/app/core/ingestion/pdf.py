"""PDF text extraction with pdfplumber and OCR fallback."""

from __future__ import annotations

import logging

import pdfplumber
from pdfminer.psparser import PSException

logger = logging.getLogger(__name__)


async def extract_pdf_text(file_path: str) -> str:
    """Extract text from a PDF using pdfplumber.

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        Concatenated text from all pages, separated by double newlines.
        Returns an empty string if no text could be extracted.
    """
    text_parts: list[str] = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                except (ValueError, TypeError, KeyError):
                    logger.warning(
                        "Failed to extract text from page %d of %s", page_num, file_path
                    )
    except (OSError, PSException, ValueError) as exc:
        logger.error("Failed to open PDF %s: %s", file_path, exc)
        return ""

    return "\n\n".join(text_parts)


async def extract_with_ocr(file_path: str) -> str:
    """Fallback OCR extraction for scanned PDFs.

    Uses pdf2image to convert pages to images and pytesseract
    for optical character recognition.

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        OCR-extracted text from all pages, separated by double newlines.
        Returns an empty string on failure.
    """
    try:
        import pytesseract
        from pdf2image import convert_from_path
        from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError
    except ImportError:
        logger.error(
            "pdf2image or pytesseract not installed. "
            "Install with: pip install pdf2image pytesseract"
        )
        return ""

    try:
        images = convert_from_path(file_path)
        text_parts: list[str] = []
        for i, img in enumerate(images, start=1):
            try:
                page_text = pytesseract.image_to_string(img)
                if page_text and page_text.strip():
                    text_parts.append(page_text)
            except (OSError, RuntimeError):
                logger.warning("OCR failed on page %d of %s", i, file_path)
        return "\n\n".join(text_parts)
    except (OSError, PDFPageCountError, PDFSyntaxError) as exc:
        logger.error("OCR extraction failed for %s: %s", file_path, exc)
        return ""
