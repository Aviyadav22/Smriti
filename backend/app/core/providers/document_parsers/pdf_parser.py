"""PDF document parser provider implementation."""

from __future__ import annotations

import asyncio
import logging
import os

import pdfplumber
import pytesseract
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)


def _extract_text_sync(file_path: str) -> str:
    """Synchronous text extraction via pdfplumber."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    text_parts: list[str] = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                except Exception as exc:
                    logger.warning(
                        "Failed to extract text from page %d of '%s': %s",
                        page_num,
                        file_path,
                        exc,
                    )
                    # Continue with remaining pages
    except pdfplumber.pdfminer.pdfparser.PDFSyntaxError as exc:
        raise RuntimeError(
            f"Invalid or corrupted PDF file '{file_path}': {exc}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Failed to open/parse PDF '{file_path}': {exc}"
        ) from exc

    if not text_parts:
        logger.warning("No text extracted from PDF '%s' (may be scanned/image-only)", file_path)

    return "\n\n".join(text_parts)


def _extract_text_with_ocr_sync(file_path: str) -> str:
    """Synchronous OCR text extraction via pdf2image + pytesseract."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    try:
        images = convert_from_path(file_path)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to convert PDF to images for OCR '{file_path}': {exc}"
        ) from exc

    text_parts: list[str] = []
    for page_num, img in enumerate(images, start=1):
        try:
            page_text = pytesseract.image_to_string(img)
            if page_text and page_text.strip():
                text_parts.append(page_text)
        except Exception as exc:
            logger.warning(
                "OCR failed on page %d of '%s': %s",
                page_num,
                file_path,
                exc,
            )
            # Continue with remaining pages

    if not text_parts:
        logger.warning("OCR extracted no text from PDF '%s'", file_path)

    return "\n\n".join(text_parts)


class PDFParser:
    """PDF parser implementing DocumentParser protocol."""

    async def extract_text(self, file_path: str) -> str:
        """Extract text from a PDF using pdfplumber.

        Runs in a thread to avoid blocking the event loop.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            RuntimeError: If PDF parsing fails.
        """
        return await asyncio.to_thread(_extract_text_sync, file_path)

    async def extract_text_with_ocr(self, file_path: str) -> str:
        """Extract text from a scanned PDF using OCR.

        Runs in a thread to avoid blocking the event loop.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            RuntimeError: If OCR processing fails.
        """
        return await asyncio.to_thread(_extract_text_with_ocr_sync, file_path)
