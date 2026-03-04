"""Document parser interface for text extraction."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class DocumentParser(Protocol):
    """Contract for document parsing providers."""

    async def extract_text(self, file_path: str) -> str: ...

    async def extract_text_with_ocr(self, file_path: str) -> str: ...
