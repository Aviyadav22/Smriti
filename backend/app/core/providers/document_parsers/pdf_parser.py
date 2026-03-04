"""PDF document parser provider implementation."""

from __future__ import annotations

import pdfplumber
import pytesseract
from pdf2image import convert_from_path


class PDFParser:
    """PDF parser implementing DocumentParser protocol."""

    async def extract_text(self, file_path: str) -> str:
        """Extract text from a PDF using pdfplumber."""
        text_parts: list[str] = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)

    async def extract_text_with_ocr(self, file_path: str) -> str:
        """Extract text from a scanned PDF using OCR."""
        images = convert_from_path(file_path)
        text_parts = [pytesseract.image_to_string(img) for img in images]
        return "\n\n".join(text_parts)
