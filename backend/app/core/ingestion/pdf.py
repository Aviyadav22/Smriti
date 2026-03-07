"""PDF text extraction with pdfplumber and OCR fallback."""

from __future__ import annotations

import asyncio
import logging

import pdfplumber
from pdfminer.psparser import PSException

logger = logging.getLogger(__name__)

# Safety limit: refuse to process PDFs with more pages than this
MAX_PAGES = 5000

# OCR batch size to avoid memory exhaustion on large scanned PDFs
_OCR_BATCH_SIZE = 10


def _extract_pdf_text_sync(file_path: str) -> str:
    """Synchronous PDF text extraction (blocking I/O)."""
    text_parts: list[str] = []
    try:
        with pdfplumber.open(file_path) as pdf:
            if len(pdf.pages) > MAX_PAGES:
                logger.error(
                    "PDF %s has %d pages, exceeds MAX_PAGES=%d",
                    file_path, len(pdf.pages), MAX_PAGES,
                )
                return ""
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


async def extract_pdf_text(file_path: str) -> str:
    """Extract text from a PDF using pdfplumber.

    Runs blocking I/O in a thread to avoid blocking the event loop.

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        Concatenated text from all pages, separated by double newlines.
        Returns an empty string if no text could be extracted.
    """
    return await asyncio.to_thread(_extract_pdf_text_sync, file_path)


async def extract_with_ocr(file_path: str) -> str:
    """Fallback OCR extraction for scanned PDFs.

    Uses pdf2image to convert pages to images and pytesseract
    for optical character recognition. Processes pages in batches
    to avoid memory exhaustion on large PDFs.

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

    def _ocr_sync() -> str:
        try:
            images = convert_from_path(file_path)
            if len(images) > MAX_PAGES:
                logger.error(
                    "PDF %s has %d pages for OCR, exceeds MAX_PAGES=%d",
                    file_path, len(images), MAX_PAGES,
                )
                return ""
            text_parts: list[str] = []
            # Process in batches to avoid memory bomb
            for batch_start in range(0, len(images), _OCR_BATCH_SIZE):
                batch = images[batch_start : batch_start + _OCR_BATCH_SIZE]
                for i, img in enumerate(batch, start=batch_start + 1):
                    try:
                        page_text = pytesseract.image_to_string(img)
                        if page_text and page_text.strip():
                            text_parts.append(page_text)
                    except (OSError, RuntimeError):
                        logger.warning("OCR failed on page %d of %s", i, file_path)
                    finally:
                        img.close()
            return "\n\n".join(text_parts)
        except (OSError, PDFPageCountError, PDFSyntaxError) as exc:
            logger.error("OCR extraction failed for %s: %s", file_path, exc)
            return ""

    return await asyncio.to_thread(_ocr_sync)
