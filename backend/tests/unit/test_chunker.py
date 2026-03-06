"""Unit tests for legal-aware text chunking."""

import pytest

from app.core.ingestion.chunker import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    Chunk,
    Section,
    chunk_judgment,
    detect_judgment_sections,
)

# Sample judgment text with clear section boundaries.
SAMPLE_JUDGMENT = """IN THE SUPREME COURT OF INDIA

CIVIL APPEAL NO. 1234 OF 2023

Petitioner v. Respondent

JUDGMENT

This is the header portion of the judgment with case details.

FACTS

The appellant filed a case regarding property dispute. The property
was located in Mumbai and had been in the family for three generations.
The dispute arose when the respondent claimed ownership based on a
forged document. The trial court examined the evidence and found in
favor of the appellant. However, the High Court reversed this finding.

ARGUMENTS

Learned counsel for the appellant submitted that the High Court erred
in its appreciation of evidence. The counsel argued that the forged
document should not have been admitted. The respondent's counsel
contended that the document was genuine and properly authenticated.

ANALYSIS AND DISCUSSION

We have considered the submissions of both parties. After careful
examination of the evidence on record, we find that the trial court
had correctly appreciated the evidence. The High Court committed an
error in reversing the finding without adequate reasons.

RATIO DECIDENDI

We hold that a forged document cannot be the basis for claiming
ownership of property. The burden of proof lies on the party
relying on such document.

ORDER

In the result, the appeal is allowed. The judgment of the High Court
is set aside and the trial court judgment is restored. No costs.
"""


class TestDetectJudgmentSections:
    """Tests for detect_judgment_sections()."""

    def test_detects_main_sections(self):
        sections = detect_judgment_sections(SAMPLE_JUDGMENT)
        types = [s.type for s in sections]
        assert "HEADER" in types
        assert "FACTS" in types
        assert "ARGUMENTS" in types
        assert "ORDER" in types

    def test_sections_cover_full_text(self):
        sections = detect_judgment_sections(SAMPLE_JUDGMENT)
        assert sections[0].start == 0
        assert sections[-1].end == len(SAMPLE_JUDGMENT)

    def test_sections_are_non_overlapping(self):
        sections = detect_judgment_sections(SAMPLE_JUDGMENT)
        for i in range(len(sections) - 1):
            assert sections[i].end <= sections[i + 1].start + 1

    def test_empty_text(self):
        assert detect_judgment_sections("") == []

    def test_no_sections_found(self):
        text = "Just a plain paragraph with no legal section markers."
        sections = detect_judgment_sections(text)
        assert len(sections) == 0

    def test_section_text_not_empty(self):
        sections = detect_judgment_sections(SAMPLE_JUDGMENT)
        for section in sections:
            assert section.text.strip()


class TestChunkJudgment:
    """Tests for chunk_judgment()."""

    def test_short_text_single_chunk(self):
        text = "A short legal opinion under 2000 characters that is too brief to need splitting."
        chunks = chunk_judgment(text, case_id="test-id")
        assert len(chunks) == 1
        assert chunks[0].case_id == "test-id"
        assert chunks[0].chunk_index == 0

    def test_chunk_size_limit(self):
        # Create text longer than CHUNK_SIZE
        long_section = "word " * 1000  # ~5000 chars
        chunks = chunk_judgment(long_section, case_id="test")
        for chunk in chunks:
            assert len(chunk.text) <= CHUNK_SIZE

    def test_chunks_have_section_type(self):
        chunks = chunk_judgment(SAMPLE_JUDGMENT, case_id="test")
        for chunk in chunks:
            assert chunk.section_type in (
                "HEADER", "FACTS", "ARGUMENTS", "ISSUES",
                "ANALYSIS", "RATIO", "ORDER", "FULL",
            )

    def test_chunk_indexes_sequential(self):
        chunks = chunk_judgment(SAMPLE_JUDGMENT, case_id="test")
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_empty_text_no_chunks(self):
        assert chunk_judgment("", case_id="test") == []

    def test_custom_sections_respected(self):
        text = "Part A content here. " * 100 + "Part B content here. " * 100
        custom_sections = [
            Section(type="FACTS", start=0, end=len(text) // 2, text=text[: len(text) // 2]),
            Section(type="ORDER", start=len(text) // 2, end=len(text), text=text[len(text) // 2 :]),
        ]
        chunks = chunk_judgment(text, sections=custom_sections, case_id="test")
        fact_chunks = [c for c in chunks if c.section_type == "FACTS"]
        order_chunks = [c for c in chunks if c.section_type == "ORDER"]
        assert len(fact_chunks) > 0
        assert len(order_chunks) > 0


class TestChunkingParameters:
    """Verify chunking parameters match spec."""

    def test_chunk_size_is_2000(self):
        assert CHUNK_SIZE == 2000

    def test_chunk_overlap_is_200(self):
        assert CHUNK_OVERLAP == 200
