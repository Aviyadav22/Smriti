"""Ingestion pipeline for Indian court judgments."""

from app.core.ingestion.chunker import Chunk, Section, chunk_judgment, detect_judgment_sections
from app.core.ingestion.metadata import CaseMetadata, extract_metadata_llm, merge_metadata, validate_with_regex
from app.core.ingestion.pdf import extract_pdf_text, extract_with_ocr
from app.core.ingestion.pipeline import ingest_judgment

__all__ = [
    "CaseMetadata",
    "Chunk",
    "Section",
    "chunk_judgment",
    "detect_judgment_sections",
    "extract_metadata_llm",
    "extract_pdf_text",
    "extract_with_ocr",
    "ingest_judgment",
    "merge_metadata",
    "validate_with_regex",
]
