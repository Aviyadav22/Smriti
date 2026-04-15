"""Tests for Phase 5 prompt constants."""

from app.core.legal.prompts import (
    AUDIO_SUMMARY_SYSTEM,
    AUDIO_SUMMARY_USER,
    DOCUMENT_COUNTER_ARGUMENTS_USER,
    DOCUMENT_ISSUE_EXTRACTION_SCHEMA,
    DOCUMENT_ISSUE_EXTRACTION_SYSTEM,
    DOCUMENT_ISSUE_EXTRACTION_USER,
    DOCUMENT_RESEARCH_MEMO_USER,
)


class TestDocumentPrompts:
    def test_issue_extraction_system_not_empty(self) -> None:
        assert len(DOCUMENT_ISSUE_EXTRACTION_SYSTEM) > 100

    def test_issue_extraction_user_has_placeholder(self) -> None:
        assert "{document_text}" in DOCUMENT_ISSUE_EXTRACTION_USER

    def test_issue_extraction_schema_has_required_fields(self) -> None:
        required = DOCUMENT_ISSUE_EXTRACTION_SCHEMA["required"]
        assert "issues" in required
        assert "parties" in required
        assert "document_type" in required

    def test_issue_extraction_schema_issues_structure(self) -> None:
        items = DOCUMENT_ISSUE_EXTRACTION_SCHEMA["properties"]["issues"]["items"]
        assert "title" in items["properties"]
        assert "description" in items["properties"]

    def test_counter_arguments_user_has_placeholders(self) -> None:
        assert "{document_type}" in DOCUMENT_COUNTER_ARGUMENTS_USER
        assert "{issues_with_precedents}" in DOCUMENT_COUNTER_ARGUMENTS_USER

    def test_research_memo_user_has_all_placeholders(self) -> None:
        for placeholder in (
            "{document_type}",
            "{parties}",
            "{relief_sought}",
            "{key_facts}",
            "{issues_analysis}",
            "{counter_arguments}",
        ):
            assert placeholder in DOCUMENT_RESEARCH_MEMO_USER


class TestAudioPrompts:
    def test_audio_summary_system_mentions_word_count(self) -> None:
        assert "400-600" in AUDIO_SUMMARY_SYSTEM

    def test_audio_summary_user_has_placeholders(self) -> None:
        for placeholder in ("{title}", "{court}", "{year}", "{judges}", "{judgment_text}"):
            assert placeholder in AUDIO_SUMMARY_USER

    def test_audio_summary_system_mentions_spoken_delivery(self) -> None:
        assert "spoken" in AUDIO_SUMMARY_SYSTEM.lower()
