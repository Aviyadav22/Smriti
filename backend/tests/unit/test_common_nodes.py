"""Tests for shared agent node utilities in app.core.agents.nodes.common."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agents.nodes.common import (
    HINDI_SYSTEM_SUFFIX,
    MAX_RESULTS_FOR_LLM,
    apply_language_suffix,
    collect_grounding_citations,
    deduplicate_by_case_id,
    detect_overruled_cases,
    format_search_results_for_llm,
    get_latest_feedback,
    get_message_data,
    safe_json_parse,
    safe_json_parse_list,
    verify_memo_citations,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_max_results_for_llm(self) -> None:
        assert MAX_RESULTS_FOR_LLM == 30

    def test_hindi_suffix_exists(self) -> None:
        assert "Hindi" in HINDI_SYSTEM_SUFFIX
        assert "Devanagari" in HINDI_SYSTEM_SUFFIX


# ---------------------------------------------------------------------------
# apply_language_suffix
# ---------------------------------------------------------------------------


class TestApplyLanguageSuffix:
    def test_hindi_appends_suffix(self) -> None:
        result = apply_language_suffix("Base prompt", "hi")
        assert result.startswith("Base prompt")
        assert "Hindi" in result

    def test_english_no_change(self) -> None:
        result = apply_language_suffix("Base prompt", "en")
        assert result == "Base prompt"

    def test_unknown_language_no_change(self) -> None:
        result = apply_language_suffix("Base prompt", "fr")
        assert result == "Base prompt"


# ---------------------------------------------------------------------------
# get_latest_feedback
# ---------------------------------------------------------------------------


class TestGetLatestFeedback:
    def test_returns_none_for_empty_messages(self) -> None:
        assert get_latest_feedback([], "plan") is None

    def test_returns_none_when_no_matching_step(self) -> None:
        messages = [
            {"type": "user_feedback", "step": "memo", "content": "revise"},
        ]
        assert get_latest_feedback(messages, "plan") is None

    def test_returns_content_for_matching_step(self) -> None:
        messages = [
            {"type": "user_feedback", "step": "plan", "content": "add more"},
        ]
        assert get_latest_feedback(messages, "plan") == "add more"

    def test_returns_latest_when_multiple(self) -> None:
        messages = [
            {"type": "user_feedback", "step": "plan", "content": "first"},
            {"type": "user_feedback", "step": "plan", "content": "second"},
        ]
        assert get_latest_feedback(messages, "plan") == "second"

    def test_ignores_non_feedback_messages(self) -> None:
        messages = [
            {"type": "classification", "data": {}},
            {"type": "user_feedback", "step": "plan", "content": "match"},
        ]
        assert get_latest_feedback(messages, "plan") == "match"


# ---------------------------------------------------------------------------
# get_message_data
# ---------------------------------------------------------------------------


class TestGetMessageData:
    def test_returns_none_for_empty(self) -> None:
        assert get_message_data([], "classification") is None

    def test_returns_data_for_matching_type(self) -> None:
        messages = [
            {"type": "classification", "data": {"topic": "criminal"}},
        ]
        assert get_message_data(messages, "classification") == {"topic": "criminal"}

    def test_returns_latest_match(self) -> None:
        messages = [
            {"type": "classification", "data": {"v": 1}},
            {"type": "classification", "data": {"v": 2}},
        ]
        assert get_message_data(messages, "classification") == {"v": 2}


# ---------------------------------------------------------------------------
# deduplicate_by_case_id
# ---------------------------------------------------------------------------


class TestDeduplicateByCaseId:
    def test_empty_list(self) -> None:
        assert deduplicate_by_case_id([]) == []

    def test_keeps_highest_score(self) -> None:
        results = [
            {"case_id": "a", "score": 0.5, "title": "low"},
            {"case_id": "a", "score": 0.9, "title": "high"},
        ]
        deduped = deduplicate_by_case_id(results)
        assert len(deduped) == 1
        assert deduped[0]["title"] == "high"

    def test_multiple_case_ids(self) -> None:
        results = [
            {"case_id": "a", "score": 0.5},
            {"case_id": "b", "score": 0.7},
            {"case_id": "a", "score": 0.9},
        ]
        deduped = deduplicate_by_case_id(results)
        assert len(deduped) == 2

    def test_skips_empty_case_id(self) -> None:
        results = [{"case_id": "", "score": 0.5}]
        assert deduplicate_by_case_id(results) == []


# ---------------------------------------------------------------------------
# detect_overruled_cases
# ---------------------------------------------------------------------------


class TestDetectOverruledCases:
    def test_empty_results(self) -> None:
        assert detect_overruled_cases([]) == set()

    @patch("app.core.agents.nodes.common.has_overruling_language", return_value=True)
    def test_detects_overruled(self, mock_check: MagicMock) -> None:
        results = [
            {"case_id": "abc", "snippet": "overruled by larger bench"},
        ]
        overruled = detect_overruled_cases(results)
        assert "abc" in overruled

    @patch("app.core.agents.nodes.common.has_overruling_language", return_value=False)
    def test_no_overruling(self, mock_check: MagicMock) -> None:
        results = [
            {"case_id": "abc", "snippet": "normal case"},
        ]
        assert detect_overruled_cases(results) == set()

    def test_skips_empty_case_id(self) -> None:
        results = [{"case_id": "", "snippet": "overruled"}]
        assert detect_overruled_cases(results) == set()


# ---------------------------------------------------------------------------
# collect_grounding_citations
# ---------------------------------------------------------------------------


class TestCollectGroundingCitations:
    def test_empty_results(self) -> None:
        assert collect_grounding_citations([]) == []

    def test_collects_citations(self) -> None:
        results = [
            {"citation": "(2020) 5 SCC 1", "snippet": ""},
            {"citation": "", "snippet": ""},
            {"citation": "AIR 2019 SC 100", "snippet": ""},
        ]
        citations = collect_grounding_citations(results)
        assert "(2020) 5 SCC 1" in citations
        assert "AIR 2019 SC 100" in citations


# ---------------------------------------------------------------------------
# safe_json_parse
# ---------------------------------------------------------------------------


class TestSafeJsonParse:
    def test_valid_json_object(self) -> None:
        assert safe_json_parse('{"key": "value"}') == {"key": "value"}

    def test_valid_json_array(self) -> None:
        assert safe_json_parse("[1, 2, 3]") == [1, 2, 3]

    def test_markdown_fenced_json(self) -> None:
        raw = '```json\n{"key": "value"}\n```'
        assert safe_json_parse(raw) == {"key": "value"}

    def test_embedded_json(self) -> None:
        raw = 'Here is the result: {"key": "value"} end.'
        assert safe_json_parse(raw) == {"key": "value"}

    def test_invalid_returns_default(self) -> None:
        assert safe_json_parse("not json") == {}

    def test_custom_default(self) -> None:
        assert safe_json_parse("not json", default=[]) == []


class TestSafeJsonParseList:
    def test_returns_list(self) -> None:
        assert safe_json_parse_list('[{"a": 1}]') == [{"a": 1}]

    def test_wraps_object_in_list(self) -> None:
        assert safe_json_parse_list('{"a": 1}') == [{"a": 1}]

    def test_returns_empty_list_on_failure(self) -> None:
        assert safe_json_parse_list("not json") == []


# ---------------------------------------------------------------------------
# format_search_results_for_llm
# ---------------------------------------------------------------------------


class TestFormatSearchResultsForLlm:
    def test_empty_results(self) -> None:
        assert format_search_results_for_llm([]) == "No results found."

    def test_basic_formatting(self) -> None:
        results = [
            {
                "title": "Case A",
                "citation": "(2020) 1 SCC 1",
                "court": "Supreme Court of India",
                "year": 2020,
                "snippet": "Relevant text",
            },
        ]
        text = format_search_results_for_llm(results)
        assert "Case A" in text
        assert "(2020) 1 SCC 1" in text
        assert "Supreme Court of India" in text

    def test_bench_type_label(self) -> None:
        results = [
            {
                "title": "Case B",
                "citation": "N/A",
                "court": "Supreme Court",
                "bench_type": "constitutional",
                "year": 2021,
            },
        ]
        text = format_search_results_for_llm(results)
        assert "Constitution Bench" in text


# ---------------------------------------------------------------------------
# verify_memo_citations (async)
# ---------------------------------------------------------------------------


class TestVerifyMemoCitations:
    @pytest.mark.asyncio
    async def test_empty_memo_returns_empty(self) -> None:
        db = AsyncMock()
        result = await verify_memo_citations("", db, [])
        assert result == ""

    @pytest.mark.asyncio
    async def test_memo_without_citations_unchanged(self) -> None:
        db = AsyncMock()
        memo = "This is a plain memo with no citations."
        result = await verify_memo_citations(memo, db, [])
        assert result == memo
