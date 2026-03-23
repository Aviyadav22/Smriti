"""Unit tests for legal-aware text chunking."""

import pytest

from app.core.ingestion.chunker import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    Chunk,
    Section,
    _detect_opinion_authors,
    _detect_paragraph_range,
    _find_break_point,
    _is_abbreviation,
    _is_heading_position,
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
                "DISSENT", "CONCURRENCE", "PRELIMINARY",
                "EVIDENCE", "STATUTORY", "DIRECTIONS", "PER_CURIAM",
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


# ---------------------------------------------------------------------------
# B1: Legal abbreviation-aware sentence boundary detection
# ---------------------------------------------------------------------------


class TestLegalAbbreviationBreakPoint:
    """B1: Sentence break should not split on legal abbreviations."""

    def test_ipc_not_sentence_break(self):
        """Text with I.P.C. should not break at the abbreviation period."""
        text = "The offence under I.P.C. Section 302 is punishable with death. The court held otherwise."
        # The break should happen at "death. " not at "I.P.C. "
        bp = _find_break_point(text, 0, len(text))
        # Should break at "death. " (position after the period+space)
        assert bp == len(text) or text[bp - 2:bp] == ". "
        # The break should NOT be right after "I.P.C. "
        ipc_pos = text.index("I.P.C. ")
        assert bp != ipc_pos + 6  # "I.P.C. " is 7 chars, period at +5

    def test_crpc_not_sentence_break(self):
        """Cr.P.C. should not cause a false sentence break."""
        assert _is_abbreviation("under Cr.P.C.", 12)

    def test_vs_not_sentence_break(self):
        """vs. should not cause a false sentence break."""
        assert _is_abbreviation("State vs.", 8)

    def test_real_sentence_end_still_breaks(self):
        """A genuine sentence-ending period should still work as break point."""
        assert not _is_abbreviation("The court held so.", 17)

    def test_dr_abbreviation(self):
        """Dr. should be recognized as abbreviation."""
        assert _is_abbreviation("Dr.", 2)

    def test_single_letter_abbreviation(self):
        """Single capital letter like 'J.' should be recognized."""
        assert _is_abbreviation("K.", 1)

    def test_scc_abbreviation(self):
        """S.C.C. should be recognized as abbreviation."""
        assert _is_abbreviation("in S.C.C.", 8)

    def test_find_break_skips_abbreviation(self):
        """_find_break_point should skip abbreviation periods and find real sentence end."""
        # Build text where the only ". " is after an abbreviation, plus a real sentence end earlier
        text = "A" * 500 + "The court decided the matter. " + "The accused was charged under I.P.C. Section 302 of the code"
        bp = _find_break_point(text, 0, len(text))
        # Should break at "matter. " not "I.P.C. "
        assert "matter. " in text[bp - 8:bp] or bp == len(text)


# ---------------------------------------------------------------------------
# B2: Paragraph number detection for all Indian formats
# ---------------------------------------------------------------------------


class TestParagraphNumberDetection:
    """B2: Detect paragraph numbers in multiple Indian formats."""

    def test_dot_format(self):
        """Standard '1. text' format."""
        text = "1. The appellant filed a case.\n2. The respondent denied."
        para_start, para_end = _detect_paragraph_range(text)
        assert para_start == 1
        assert para_end == 2

    def test_paren_format(self):
        """Parenthesized '(1) text' format."""
        text = "(1) The appellant filed a case.\n(5) The respondent denied."
        para_start, para_end = _detect_paragraph_range(text)
        assert para_start == 1
        assert para_end == 5

    def test_bracket_format(self):
        """Bracketed '[1] text' format."""
        text = "[3] The court observed.\n[7] It was further held."
        para_start, para_end = _detect_paragraph_range(text)
        assert para_start == 3
        assert para_end == 7

    def test_closing_paren_format(self):
        """'1) text' format (digit followed by closing paren)."""
        text = "1) First point.\n2) Second point."
        para_start, para_end = _detect_paragraph_range(text)
        assert para_start == 1
        assert para_end == 2

    def test_para_keyword_format(self):
        """'Para 1' and 'Para. 2' formats."""
        text = "Para 10 The court held that...\nPara. 15 It was observed..."
        para_start, para_end = _detect_paragraph_range(text)
        assert para_start == 10
        assert para_end == 15

    def test_mixed_formats(self):
        """Different formats in the same text."""
        text = "1. First paragraph.\n(2) Second paragraph.\n[3] Third paragraph."
        para_start, para_end = _detect_paragraph_range(text)
        assert para_start == 1
        assert para_end == 3

    def test_no_paragraphs(self):
        """Text without paragraph numbers."""
        text = "This is plain text without any paragraph numbering."
        para_start, para_end = _detect_paragraph_range(text)
        assert para_start is None
        assert para_end is None


# ---------------------------------------------------------------------------
# B3: New section types detection
# ---------------------------------------------------------------------------


class TestNewSectionTypes:
    """B3: Detect newly added section types."""

    def test_evidence_section(self):
        text = "EVIDENCE\n\nThe witness testified that the accused was present."
        sections = detect_judgment_sections(text)
        types = [s.type for s in sections]
        assert "EVIDENCE" in types

    def test_evidence_on_record(self):
        text = "EVIDENCE ON RECORD\n\nExhibit A was produced before the court."
        sections = detect_judgment_sections(text)
        types = [s.type for s in sections]
        assert "EVIDENCE" in types

    def test_appreciation_of_evidence(self):
        text = "APPRECIATION OF EVIDENCE\n\nThe trial court considered all evidence."
        sections = detect_judgment_sections(text)
        types = [s.type for s in sections]
        assert "EVIDENCE" in types

    def test_statutory_framework(self):
        text = "STATUTORY FRAMEWORK\n\nSection 302 of IPC deals with murder."
        sections = detect_judgment_sections(text)
        types = [s.type for s in sections]
        assert "STATUTORY" in types

    def test_relevant_provisions(self):
        text = "RELEVANT PROVISIONS\n\nThe relevant provision reads as follows."
        sections = detect_judgment_sections(text)
        types = [s.type for s in sections]
        assert "STATUTORY" in types

    def test_directions_section(self):
        text = "DIRECTIONS ISSUED\n\nThe court directs the authorities to comply."
        sections = detect_judgment_sections(text)
        types = [s.type for s in sections]
        assert "DIRECTIONS" in types

    def test_relief_granted(self):
        text = "RELIEF GRANTED\n\nThe petitioner is awarded compensation."
        sections = detect_judgment_sections(text)
        types = [s.type for s in sections]
        assert "DIRECTIONS" in types

    def test_per_curiam(self):
        text = "PER CURIAM\n\nThis court unanimously holds that the appeal is dismissed."
        sections = detect_judgment_sections(text)
        types = [s.type for s in sections]
        assert "PER_CURIAM" in types

    def test_by_the_court(self):
        text = "BY THE COURT\n\nWe are of the view that the matter requires reconsideration."
        sections = detect_judgment_sections(text)
        types = [s.type for s in sections]
        assert "PER_CURIAM" in types

    def test_preliminary_section(self):
        text = "PRELIMINARY\n\nBefore addressing the merits, certain procedural issues."
        sections = detect_judgment_sections(text)
        types = [s.type for s in sections]
        assert "PRELIMINARY" in types

    def test_the_law_section(self):
        text = "THE LAW\n\nThe applicable legal framework is as follows."
        sections = detect_judgment_sections(text)
        types = [s.type for s in sections]
        assert "STATUTORY" in types


# ---------------------------------------------------------------------------
# B4: Overlap snaps to sentence boundary
# ---------------------------------------------------------------------------


class TestOverlapSentenceBoundary:
    """B4: Overlap start should snap to nearest sentence boundary."""

    def test_overlap_starts_at_sentence_boundary(self):
        """When chunking long text, overlap should start at a sentence boundary."""
        # Create text with clear sentence boundaries, longer than CHUNK_SIZE
        sentences = []
        for i in range(100):
            sentences.append(f"Sentence number {i} discusses the legal principle of equity. ")
        text = "".join(sentences)
        chunks = chunk_judgment(text, case_id="test")

        if len(chunks) > 1:
            # Second chunk should start at a sentence boundary (after ". ")
            second_chunk_text = chunks[1].text
            # The chunk should not start with a partial word fragment
            assert not second_chunk_text[0].islower() or second_chunk_text.startswith("number")
            # It should start with "Sentence" (a sentence boundary)
            assert second_chunk_text.strip().startswith("Sentence")

    def test_overlap_not_mid_word(self):
        """Overlap should not start in the middle of a word."""
        # Create text where naive overlap would land mid-word
        text = "The court observed. " * 200  # ~4000 chars
        chunks = chunk_judgment(text, case_id="test")

        for chunk in chunks:
            stripped = chunk.text.strip()
            # Each chunk should start with "The" (beginning of a sentence)
            assert stripped.startswith("The"), f"Chunk starts with: {stripped[:20]}"


# ---------------------------------------------------------------------------
# B17: Cross-type proximity dedup
# ---------------------------------------------------------------------------


class TestCrossTypeProximityDedup:
    """B17: Same-type dedup at 50 chars, different-type at 20 chars."""

    def test_same_type_within_50_chars_deduped(self):
        """Two FACTS markers within 30 chars should be deduped (same type, < 50)."""
        # "FACTS" at position 0 and "BRIEF FACTS" at position 30 — same type, distance 30 < 50
        text = "FACTS\n" + " " * 24 + "BRIEF FACTS\nSome content follows here."
        sections = detect_judgment_sections(text)
        facts_sections = [s for s in sections if s.type == "FACTS"]
        assert len(facts_sections) == 1

    def test_different_type_beyond_20_chars_kept(self):
        """FACTS and ARGUMENTS markers 30 chars apart should both be kept (different type, >= 20)."""
        text = "FACTS\n" + " " * 24 + "\nARGUMENTS\nSome detailed arguments here."
        sections = detect_judgment_sections(text)
        types = [s.type for s in sections]
        assert "FACTS" in types
        assert "ARGUMENTS" in types

    def test_different_type_within_20_chars_deduped(self):
        """FACTS and ARGUMENTS within 10 chars should be deduped (different type, < 20)."""
        # Very close markers (within 20 chars)
        text = "FACTS\n" + " " * 4 + "ARGUMENTS\nContent here."
        sections = detect_judgment_sections(text)
        types = [s.type for s in sections]
        # One of them should be deduped — only first should survive
        facts_count = types.count("FACTS")
        args_count = types.count("ARGUMENTS")
        # Total of FACTS + ARGUMENTS should be 1 (second deduped)
        assert facts_count + args_count == 1

    def test_same_type_beyond_50_chars_kept(self):
        """Two FACTS markers 60 chars apart should both be kept (same type, >= 50)."""
        text = "FACTS\n" + "x" * 54 + "\nFACTS\nMore content here for the second facts section."
        sections = detect_judgment_sections(text)
        facts_sections = [s for s in sections if s.type == "FACTS"]
        assert len(facts_sections) == 2


# ---------------------------------------------------------------------------
# C9: Per-judge opinion separation
# ---------------------------------------------------------------------------


class TestDetectOpinionAuthors:
    """C9: Detect judge name headers marking opinion boundaries."""

    def test_standard_judge_format(self):
        """D.Y. CHANDRACHUD, J. should be detected."""
        text = "Some preamble.\nD.Y. CHANDRACHUD, J.\nThe court held that..."
        authors = _detect_opinion_authors(text)
        assert len(authors) == 1
        assert authors[0][1] == "D.Y. CHANDRACHUD"

    def test_cji_format(self):
        """D.Y. CHANDRACHUD, CJI should be detected."""
        text = "D.Y. CHANDRACHUD, CJI\nThis is the majority opinion."
        authors = _detect_opinion_authors(text)
        assert len(authors) == 1
        assert authors[0][1] == "D.Y. CHANDRACHUD"

    def test_per_prefix(self):
        """Per S. RAVINDRA BHAT, J. should be detected."""
        text = "Per S. RAVINDRA BHAT, J.\nThe learned judge observed..."
        authors = _detect_opinion_authors(text)
        assert len(authors) == 1
        assert authors[0][1] == "S. RAVINDRA BHAT"

    def test_bracketed_per(self):
        """[Per B.V. NAGARATHNA, J.] should be detected."""
        text = "[Per B.V. NAGARATHNA, J.]\nIn my considered opinion..."
        authors = _detect_opinion_authors(text)
        assert len(authors) == 1
        assert authors[0][1] == "B.V. NAGARATHNA"

    def test_parenthesized_per(self):
        """(Per Dr. D.Y. Chandrachud, CJI) should be detected."""
        text = "(Per Dr. D.Y. Chandrachud, CJI)\nThe constitutional bench held..."
        authors = _detect_opinion_authors(text)
        assert len(authors) == 1
        assert "Chandrachud" in authors[0][1]

    def test_multiple_authors(self):
        """Multiple opinion boundaries should be detected in order."""
        text = (
            "D.Y. CHANDRACHUD, CJI\n"
            + "This is the majority opinion text.\n" * 5
            + "S. RAVINDRA BHAT, J.\n"
            + "This is the concurring opinion.\n" * 5
        )
        authors = _detect_opinion_authors(text)
        assert len(authors) == 2
        assert authors[0][1] == "D.Y. CHANDRACHUD"
        assert authors[1][1] == "S. RAVINDRA BHAT"
        assert authors[0][0] < authors[1][0]

    def test_no_authors(self):
        """Plain text without judge headers returns empty list."""
        text = "This is a simple text with no judge headers at all."
        authors = _detect_opinion_authors(text)
        assert authors == []

    def test_short_name_filtered(self):
        """Very short matches (<=2 chars) should be filtered out."""
        # "J." alone on a line should not match meaningfully
        text = "Some text here.\nJ.\nMore text."
        authors = _detect_opinion_authors(text)
        # Should be empty since the captured name group would be too short
        assert len(authors) == 0


class TestOpinionAuthorOnChunks:
    """C9: Chunks should carry the correct opinion_author."""

    def test_multi_opinion_chunks(self):
        """Chunks from a multi-opinion judgment get correct opinion_author."""
        opinion_a = "A.B. SAPRE, J.\n" + "First judge's analysis. " * 100
        opinion_b = "R.F. NARIMAN, J.\n" + "Second judge's dissent. " * 100
        text = opinion_a + "\n" + opinion_b
        chunks = chunk_judgment(text, case_id="test-opinion")
        assert len(chunks) > 1

        # Find the boundary: chunks with first author vs second
        first_author_chunks = [c for c in chunks if c.opinion_author == "A.B. SAPRE"]
        second_author_chunks = [c for c in chunks if c.opinion_author == "R.F. NARIMAN"]
        assert len(first_author_chunks) > 0, "Should have chunks attributed to first judge"
        assert len(second_author_chunks) > 0, "Should have chunks attributed to second judge"

        # First author chunks should come before second author chunks
        max_first_idx = max(c.chunk_index for c in first_author_chunks)
        min_second_idx = min(c.chunk_index for c in second_author_chunks)
        assert max_first_idx < min_second_idx

    def test_single_opinion_author(self):
        """Single opinion text should attribute all chunks to that author."""
        text = "D.Y. CHANDRACHUD, CJI\n" + "The court held that this matter. " * 50
        chunks = chunk_judgment(text, case_id="test-single")
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.opinion_author == "D.Y. CHANDRACHUD"

    def test_no_opinion_header_gives_none(self):
        """Text without opinion headers should have opinion_author=None."""
        text = "This is a regular judgment text without any judge headers. " * 50
        chunks = chunk_judgment(text, case_id="test-none")
        for chunk in chunks:
            assert chunk.opinion_author is None

    def test_chunk_dataclass_has_opinion_author_field(self):
        """The Chunk dataclass should have the opinion_author field."""
        chunk = Chunk(
            text="test",
            section_type="FULL",
            chunk_index=0,
            case_id="test",
            opinion_author="D.Y. CHANDRACHUD",
        )
        assert chunk.opinion_author == "D.Y. CHANDRACHUD"

    def test_chunk_opinion_author_defaults_to_none(self):
        """opinion_author should default to None."""
        chunk = Chunk(
            text="test",
            section_type="FULL",
            chunk_index=0,
            case_id="test",
        )
        assert chunk.opinion_author is None


class TestIsHeadingPositionLineLengthHeuristic:
    """Tests for line-length heuristic in _is_heading_position."""

    def test_long_line_with_evidence_keyword_is_not_heading(self):
        """'15. Evidence shows that the accused...' should NOT match as EVIDENCE heading."""
        text = "Some text above.\n15. Evidence shows that the accused was present at the scene of the crime on the night of the incident and was seen by multiple witnesses"
        # Find where 'Evidence' starts in the text
        match_start = text.index("Evidence")
        assert _is_heading_position(text, match_start) is False

    def test_short_line_is_heading(self):
        """A short line like 'EVIDENCE' at line start IS a heading."""
        text = "Some text above.\nEVIDENCE\nThe court considered..."
        match_start = text.index("EVIDENCE")
        assert _is_heading_position(text, match_start) is True

    def test_numbered_short_line_is_heading(self):
        """'III. EVIDENCE' should be detected as heading."""
        text = "Some text above.\nIII. EVIDENCE\nThe court considered..."
        match_start = text.index("EVIDENCE")
        assert _is_heading_position(text, match_start) is True


# ---------------------------------------------------------------------------
# V3: Section-aware chunking + legal signal scoring
# ---------------------------------------------------------------------------


def test_dense_sections_get_smaller_chunks():
    from app.core.ingestion.chunker import chunk_judgment, Section
    # Create a long ANALYSIS section (3000 chars)
    analysis_text = "The court held that " * 150  # ~3000 chars
    sections = [Section(type="ANALYSIS", start=0, end=len(analysis_text), text=analysis_text)]
    chunks = chunk_judgment(analysis_text, sections, case_id="test")
    # With 1200-char chunks, should produce 3+ chunks (not 2 as with 2000-char)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk.text) <= 1200 + 50  # small tolerance for break-point adjustment


def test_legal_signal_scoring():
    from app.core.ingestion.chunker import _compute_legal_signal
    high = _compute_legal_signal("We held that the appeal is dismissed. In our opinion, the principle is well settled.")
    low = _compute_legal_signal("The petitioner filed a complaint on 15th March 2020 regarding the property dispute.")
    assert high > low
    assert high > 0
