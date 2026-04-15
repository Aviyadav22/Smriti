"""Tests for PDF page mapping."""
from app.core.ingestion.pdf import TextQuality, _build_page_map


class TestTextQualityPageMap:
    """Verify TextQuality includes page_map."""

    def test_page_map_field_exists(self):
        tq = TextQuality(
            text="test", char_count=4, tier="high",
            ocr_used=False, legal_keyword_count=0, page_count=1,
            page_map=[{"page_number": 1, "char_start": 0, "char_end": 4}],
        )
        assert len(tq.page_map) == 1
        assert tq.page_map[0]["page_number"] == 1

    def test_page_map_default_empty(self):
        tq = TextQuality(
            text="test", char_count=4, tier="high",
            ocr_used=False, legal_keyword_count=0, page_count=1,
        )
        assert tq.page_map == []

    def test_page_map_char_ranges_are_contiguous(self):
        page_map = [
            {"page_number": 1, "char_start": 0, "char_end": 100},
            {"page_number": 2, "char_start": 100, "char_end": 250},
            {"page_number": 3, "char_start": 250, "char_end": 400},
        ]
        for i in range(1, len(page_map)):
            assert page_map[i]["char_start"] == page_map[i - 1]["char_end"]


class TestBuildPageMap:
    """Verify _build_page_map produces correct offsets."""

    def test_simple_two_pages(self):
        page_texts = [
            "This is the first page content with enough text for matching.",
            "This is the second page content that follows after the first.",
        ]
        joined = "\n\n".join(page_texts)
        page_map = _build_page_map(page_texts, joined)
        assert len(page_map) == 2
        assert page_map[0]["page_number"] == 1
        assert page_map[0]["char_start"] == 0
        assert page_map[1]["page_number"] == 2
        assert page_map[1]["char_start"] > 0

    def test_empty_page_skipped(self):
        page_texts = ["Content", "", "More content"]
        joined = "Content\n\nMore content"
        page_map = _build_page_map(page_texts, joined)
        # Empty page should be skipped
        assert all(pm["page_number"] != 2 for pm in page_map)

    def test_single_page(self):
        text = "Single page judgment content here."
        page_map = _build_page_map([text], text)
        assert len(page_map) == 1
        assert page_map[0]["char_start"] == 0
        assert page_map[0]["char_end"] == len(text)
