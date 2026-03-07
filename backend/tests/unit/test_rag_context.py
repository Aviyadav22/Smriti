"""Tests for RAG context formatting with rich case content."""

from app.core.chat.rag import (
    BENCH_LABELS,
    MAX_CHUNK_CHARS,
    MAX_RATIO_CHARS,
    ChatSource,
    _format_context,
)


def _make_source(**overrides) -> ChatSource:
    """Helper to build a ChatSource with sensible defaults."""
    defaults = {
        "case_id": "case-001",
        "title": "State of Maharashtra v. Respondent",
        "citation": "(2023) 5 SCC 123",
        "court": "Supreme Court of India",
        "year": 2023,
        "score": 0.95,
        "ratio": "The court held that fundamental rights under Article 21 are non-derogable.",
        "bench_type": "division",
        "judge_names": ["Justice A. Kumar", "Justice B. Singh"],
        "chunk_text": "The petitioner argued that the right to life includes the right to livelihood.",
    }
    defaults.update(overrides)
    return ChatSource(**defaults)


class TestFormatContext:
    """Tests for _format_context()."""

    def test_includes_ratio_decidendi(self) -> None:
        """Ratio decidendi text must appear in the formatted context."""
        sources = [_make_source()]
        result = _format_context(sources)
        assert "Ratio Decidendi:" in result
        assert "fundamental rights under Article 21" in result

    def test_includes_bench_info(self) -> None:
        """Bench type label and judge names must appear in context."""
        sources = [_make_source(bench_type="constitutional")]
        result = _format_context(sources)
        assert "Constitution Bench" in result
        assert "Justice A. Kumar" in result
        assert "Justice B. Singh" in result

    def test_includes_chunk_text(self) -> None:
        """Relevant passage (chunk text) must appear in context."""
        sources = [_make_source()]
        result = _format_context(sources)
        assert "Relevant Passage:" in result
        assert "right to life includes the right to livelihood" in result

    def test_empty_sources_returns_no_results_message(self) -> None:
        """Empty source list returns the 'no results' message."""
        result = _format_context([])
        assert result == "No relevant cases were found in the database."

    def test_missing_ratio_still_formats(self) -> None:
        """Source with no ratio should still format correctly without errors."""
        sources = [_make_source(ratio=None, chunk_text=None)]
        result = _format_context(sources)
        assert "State of Maharashtra" in result
        assert "(2023) 5 SCC 123" in result
        assert "Ratio Decidendi:" not in result
        assert "Relevant Passage:" not in result

    def test_truncates_long_ratio(self) -> None:
        """Ratio text exceeding MAX_RATIO_CHARS must be truncated with ellipsis."""
        long_ratio = "A" * (MAX_RATIO_CHARS + 500)
        sources = [_make_source(ratio=long_ratio)]
        result = _format_context(sources)
        # Should contain exactly MAX_RATIO_CHARS of 'A' plus "..."
        assert "A" * MAX_RATIO_CHARS in result
        assert "A" * (MAX_RATIO_CHARS + 1) not in result
        assert "..." in result

    def test_truncates_long_chunk_text(self) -> None:
        """Chunk text exceeding MAX_CHUNK_CHARS must be truncated with ellipsis."""
        long_chunk = "B" * (MAX_CHUNK_CHARS + 500)
        sources = [_make_source(chunk_text=long_chunk)]
        result = _format_context(sources)
        assert "B" * MAX_CHUNK_CHARS in result
        assert "B" * (MAX_CHUNK_CHARS + 1) not in result

    def test_bench_labels_all_types(self) -> None:
        """All bench type keys produce correct labels in context."""
        for key, label in BENCH_LABELS.items():
            sources = [_make_source(bench_type=key)]
            result = _format_context(sources)
            assert label in result, f"Expected '{label}' for bench_type='{key}'"

    def test_unknown_bench_type_omits_label(self) -> None:
        """Unknown bench_type should not add a parenthetical to court."""
        sources = [_make_source(bench_type="unknown_type")]
        result = _format_context(sources)
        # Court string should not have a parenthetical bench label
        assert "Supreme Court of India," in result
        assert "Single Judge" not in result
        assert "Division Bench" not in result

    def test_no_judge_names_omits_bench_line(self) -> None:
        """If judge_names is None, the Bench line should be absent."""
        sources = [_make_source(judge_names=None)]
        result = _format_context(sources)
        assert "Bench:" not in result

    def test_multiple_sources_numbered(self) -> None:
        """Multiple sources should be numbered [1], [2], etc."""
        sources = [
            _make_source(case_id="c1", title="Case Alpha"),
            _make_source(case_id="c2", title="Case Beta"),
        ]
        result = _format_context(sources)
        assert "[1] Case Alpha" in result
        assert "[2] Case Beta" in result
