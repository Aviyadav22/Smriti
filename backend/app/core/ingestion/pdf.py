"""PDF text extraction with pdfplumber and OCR fallback."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import pdfplumber
from pdfminer.psparser import PSException

logger = logging.getLogger(__name__)

# Safety limit: refuse to process PDFs with more pages than this
MAX_PAGES = 5000

# OCR batch size to avoid memory exhaustion on large scanned PDFs
_OCR_BATCH_SIZE = 10


@dataclass
class TextQuality:
    """Quality assessment of extracted text."""
    text: str
    char_count: int
    tier: str  # "high", "medium", "low"
    ocr_used: bool
    legal_keyword_count: int
    page_count: int


LEGAL_KEYWORDS = {
    "court", "petitioner", "respondent", "section", "act", "judgment",
    "order", "appeal", "bench", "hon'ble", "advocate", "counsel",
    "article", "constitution", "decree", "plaintiff", "defendant",
    "prosecution", "accused", "bail", "writ", "petition", "tribunal",
    "appellant", "versus", "v.", "vs.", "learned", "disposed",
}


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


def score_text_quality(text: str, ocr_used: bool = False, page_count: int = 0) -> TextQuality:
    """Score the quality of extracted judgment text.

    Tiers:
    - high: >2000 chars, >=3 legal keywords
    - medium: >500 chars, >=1 legal keyword
    - low: everything else (flag for manual review)
    """
    char_count = len(text)
    text_lower = text.lower()
    legal_keyword_count = sum(1 for kw in LEGAL_KEYWORDS if kw in text_lower)

    if char_count > 2000 and legal_keyword_count >= 3:
        tier = "high"
    elif char_count > 500 and legal_keyword_count >= 1:
        tier = "medium"
    else:
        tier = "low"

    return TextQuality(
        text=text,
        char_count=char_count,
        tier=tier,
        ocr_used=ocr_used,
        legal_keyword_count=legal_keyword_count,
        page_count=page_count,
    )


async def extract_and_score(file_path: str) -> TextQuality:
    """Extract text from PDF and return quality-scored result.

    Tries pdfplumber first, falls back to OCR if insufficient text.
    """
    # Get page count for metrics
    page_count = 0
    try:
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
    except (OSError, PSException, ValueError):
        pass

    text = await extract_pdf_text(file_path)
    ocr_used = False

    if not text or len(text) < 100:
        logger.warning("pdfplumber extraction insufficient, trying OCR: %s", file_path)
        text = await extract_with_ocr(file_path)
        ocr_used = True

    if not text:
        text = ""

    quality = score_text_quality(text, ocr_used=ocr_used, page_count=page_count)

    if quality.tier == "low":
        logger.warning(
            "Low quality extraction for %s: %d chars, %d legal keywords, ocr=%s",
            file_path, quality.char_count, quality.legal_keyword_count, ocr_used,
        )

    return quality
