"""PDF document parser provider implementation.

Delegates to the primary extraction module at app.core.ingestion.pdf,
which provides NFKC normalization, header/footer dedup, smart page joining,
per-page OCR fallback, and quality scoring.
"""

from __future__ import annotations

import logging

from app.core.ingestion.pdf import extract_pdf_text, extract_with_ocr

logger = logging.getLogger(__name__)


class PDFParser:
    """PDF parser implementing DocumentParser protocol.

    Thin wrapper that delegates to the primary pdf.py extraction module.
    """

    async def extract_text(self, file_path: str) -> str:
        """Extract text from a PDF using pdfplumber with per-page OCR fallback.

        Delegates to the primary extraction pipeline which includes NFKC
        normalization, header/footer deduplication, smart page joining,
        and per-page OCR fallback for low-text pages.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            RuntimeError: If PDF parsing fails.
        """
        result = await extract_pdf_text(file_path)
        # extract_pdf_text returns (text, page_count) tuple
        if isinstance(result, tuple):
            return result[0]
        return result

    async def extract_text_with_ocr(self, file_path: str) -> str:
        """Extract text from a scanned PDF using OCR.

        Delegates to the primary OCR pipeline which processes pages
        one at a time to avoid OOM, with English + Hindi language support.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            RuntimeError: If OCR processing fails.
        """
        text, _truncated, _total_pages = await extract_with_ocr(file_path)
        return text
