"""Unit tests for LLM-based query understanding."""

import pytest

from app.core.search.query import (
    QueryEntities,
    QueryUnderstanding,
    SearchFilters,
    _parse_llm_result,
    _passthrough,
    understand_query,
)


class TestPassthrough:
    """Tests for the fallback passthrough function."""

    def test_basic_passthrough(self) -> None:
        result = _passthrough("right to privacy")
        assert result.intent == "general"
        assert result.original_query == "right to privacy"
        assert result.expanded_query == "right to privacy"
        assert result.search_strategy == "balanced"
        assert result.filters.court is None
        assert result.entities.case_names == []

    def test_empty_query_passthrough(self) -> None:
        result = _passthrough("")
        assert result.original_query == ""
        assert result.expanded_query == ""


class TestParseLLMResult:
    """Tests for parsing structured LLM output."""

    def test_full_result(self) -> None:
        data = {
            "intent": "topic_search",
            "original_query": "dowry death SC after 2020",
            "expanded_query": "dowry death Section 304B IPC Supreme Court",
            "filters": {
                "court": "Supreme Court of India",
                "year_from": 2020,
                "year_to": None,
                "case_type": "Criminal Appeal",
                "bench_type": None,
                "judge": None,
                "act": "Indian Penal Code, 1860",
                "section": "304B",
            },
            "entities": {
                "case_names": [],
                "statutes": ["Indian Penal Code, 1860 - Section 304B"],
                "legal_concepts": ["dowry death", "cruelty"],
                "judges": [],
                "courts": ["Supreme Court of India"],
            },
            "search_strategy": "balanced",
        }

        result = _parse_llm_result("dowry death SC after 2020", data)

        assert result.intent == "topic_search"
        assert result.filters.court == "Supreme Court of India"
        assert result.filters.year_from == 2020
        assert result.filters.case_type == "Criminal Appeal"
        assert result.entities.statutes == ["Indian Penal Code, 1860 - Section 304B"]
        assert result.search_strategy == "balanced"

    def test_minimal_result(self) -> None:
        """Handles missing optional fields gracefully."""
        data = {
            "intent": "general",
            "original_query": "test",
            "expanded_query": "test query",
            "filters": {},
            "entities": {},
            "search_strategy": "balanced",
        }
        result = _parse_llm_result("test", data)
        assert result.intent == "general"
        assert result.filters.court is None
        assert result.entities.case_names == []

    def test_citation_lookup_intent(self) -> None:
        data = {
            "intent": "citation_lookup",
            "original_query": "Kesavananda Bharati",
            "expanded_query": "Kesavananda Bharati v State of Kerala basic structure",
            "filters": {"court": "Supreme Court of India"},
            "entities": {
                "case_names": ["Kesavananda Bharati v. State of Kerala"],
                "statutes": [],
                "legal_concepts": ["basic structure doctrine"],
                "judges": [],
                "courts": ["Supreme Court of India"],
            },
            "search_strategy": "exact_match",
        }
        result = _parse_llm_result("Kesavananda Bharati", data)
        assert result.intent == "citation_lookup"
        assert result.search_strategy == "exact_match"
        assert "Kesavananda Bharati" in result.entities.case_names[0]


class TestUnderstandQuery:
    """Tests for the full understand_query function with mock LLM."""

    @pytest.mark.asyncio
    async def test_fallback_on_llm_failure(self) -> None:
        """When LLM raises an error, returns passthrough result."""

        class FailingLLM:
            async def generate_structured(self, **kwargs) -> dict:
                raise ConnectionError("LLM unavailable")

            async def generate(self, **kwargs) -> str:
                return ""

            async def stream(self, **kwargs):
                yield ""

        result = await understand_query("test query", FailingLLM())
        assert result.intent == "general"
        assert result.original_query == "test query"
        assert result.expanded_query == "test query"

    @pytest.mark.asyncio
    async def test_successful_llm_call(self) -> None:
        """When LLM returns valid structured output, parses correctly."""

        class MockLLM:
            async def generate_structured(self, **kwargs) -> dict:
                return {
                    "intent": "topic_search",
                    "original_query": "murder SC",
                    "expanded_query": "murder homicide Section 302 IPC Supreme Court",
                    "filters": {"court": "Supreme Court of India"},
                    "entities": {
                        "case_names": [],
                        "statutes": ["Indian Penal Code, 1860 - Section 302"],
                        "legal_concepts": ["murder", "homicide"],
                        "judges": [],
                        "courts": ["Supreme Court of India"],
                    },
                    "search_strategy": "balanced",
                }

            async def generate(self, **kwargs) -> str:
                return ""

            async def stream(self, **kwargs):
                yield ""

        result = await understand_query("murder SC", MockLLM())
        assert result.intent == "topic_search"
        assert result.filters.court == "Supreme Court of India"
        assert len(result.entities.statutes) == 1
