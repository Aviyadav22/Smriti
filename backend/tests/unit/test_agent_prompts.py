"""Tests for Research Agent and Case Prep Agent prompt constants."""

import pytest

from app.core.legal.prompts import (
    # Research Agent prompts
    RESEARCH_CLASSIFY_SYSTEM,
    RESEARCH_CLASSIFY_SCHEMA,
    RESEARCH_DECOMPOSE_SYSTEM,
    RESEARCH_DECOMPOSE_USER,
    RESEARCH_DECOMPOSE_SCHEMA,
    RESEARCH_CONTRADICTIONS_SYSTEM,
    RESEARCH_SYNTHESIZE_SYSTEM,
    RESEARCH_SYNTHESIZE_USER,
    # Case Prep Agent prompts
    CASE_PREP_PRIORITIZE_SYSTEM,
    CASE_PREP_PRIORITIZE_USER,
    CASE_PREP_ARGUMENT_ORDER_SYSTEM,
    CASE_PREP_STRATEGY_SYSTEM,
    CASE_PREP_STRATEGY_USER,
)


# ---------------------------------------------------------------------------
# Research Agent — system prompts are non-empty strings (>50 chars)
# ---------------------------------------------------------------------------


class TestResearchAgentPrompts:
    """Tests for Research Agent prompt constants."""

    @pytest.mark.parametrize(
        "prompt",
        [
            RESEARCH_CLASSIFY_SYSTEM,
            RESEARCH_DECOMPOSE_SYSTEM,
            RESEARCH_CONTRADICTIONS_SYSTEM,
            RESEARCH_SYNTHESIZE_SYSTEM,
        ],
        ids=[
            "RESEARCH_CLASSIFY_SYSTEM",
            "RESEARCH_DECOMPOSE_SYSTEM",
            "RESEARCH_CONTRADICTIONS_SYSTEM",
            "RESEARCH_SYNTHESIZE_SYSTEM",
        ],
    )
    def test_system_prompts_are_nonempty_strings(self, prompt: str) -> None:
        assert isinstance(prompt, str)
        assert len(prompt) > 50, f"System prompt too short ({len(prompt)} chars)"

    @pytest.mark.parametrize(
        "prompt",
        [
            RESEARCH_DECOMPOSE_USER,
            RESEARCH_SYNTHESIZE_USER,
        ],
        ids=[
            "RESEARCH_DECOMPOSE_USER",
            "RESEARCH_SYNTHESIZE_USER",
        ],
    )
    def test_user_prompts_are_nonempty_strings(self, prompt: str) -> None:
        assert isinstance(prompt, str)
        assert len(prompt) > 50, f"User prompt too short ({len(prompt)} chars)"

    def test_decompose_user_has_placeholders(self) -> None:
        assert "{query}" in RESEARCH_DECOMPOSE_USER
        assert "{classification}" in RESEARCH_DECOMPOSE_USER

    def test_synthesize_user_has_placeholders(self) -> None:
        assert "{query}" in RESEARCH_SYNTHESIZE_USER
        assert "{findings}" in RESEARCH_SYNTHESIZE_USER
        assert "{contradictions}" in RESEARCH_SYNTHESIZE_USER


# ---------------------------------------------------------------------------
# Case Prep Agent — system prompts are non-empty strings (>50 chars)
# ---------------------------------------------------------------------------


class TestCasePrepAgentPrompts:
    """Tests for Case Prep Agent prompt constants."""

    @pytest.mark.parametrize(
        "prompt",
        [
            CASE_PREP_PRIORITIZE_SYSTEM,
            CASE_PREP_ARGUMENT_ORDER_SYSTEM,
            CASE_PREP_STRATEGY_SYSTEM,
        ],
        ids=[
            "CASE_PREP_PRIORITIZE_SYSTEM",
            "CASE_PREP_ARGUMENT_ORDER_SYSTEM",
            "CASE_PREP_STRATEGY_SYSTEM",
        ],
    )
    def test_system_prompts_are_nonempty_strings(self, prompt: str) -> None:
        assert isinstance(prompt, str)
        assert len(prompt) > 50, f"System prompt too short ({len(prompt)} chars)"

    @pytest.mark.parametrize(
        "prompt",
        [
            CASE_PREP_PRIORITIZE_USER,
            CASE_PREP_STRATEGY_USER,
        ],
        ids=[
            "CASE_PREP_PRIORITIZE_USER",
            "CASE_PREP_STRATEGY_USER",
        ],
    )
    def test_user_prompts_are_nonempty_strings(self, prompt: str) -> None:
        assert isinstance(prompt, str)
        assert len(prompt) > 50, f"User prompt too short ({len(prompt)} chars)"

    def test_prioritize_user_has_placeholders(self) -> None:
        assert "{issues}" in CASE_PREP_PRIORITIZE_USER
        assert "{parties}" in CASE_PREP_PRIORITIZE_USER
        assert "{relief_sought}" in CASE_PREP_PRIORITIZE_USER

    def test_strategy_user_has_placeholders(self) -> None:
        assert "{issues_analysis}" in CASE_PREP_STRATEGY_USER
        assert "{precedent_findings}" in CASE_PREP_STRATEGY_USER
        assert "{counter_arguments}" in CASE_PREP_STRATEGY_USER
        assert "{parties}" in CASE_PREP_STRATEGY_USER
        assert "{relief_sought}" in CASE_PREP_STRATEGY_USER


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestResearchAgentSchemas:
    """Tests for Research Agent JSON schema dicts."""

    @pytest.mark.parametrize(
        "schema",
        [
            RESEARCH_CLASSIFY_SCHEMA,
            RESEARCH_DECOMPOSE_SCHEMA,
        ],
        ids=[
            "RESEARCH_CLASSIFY_SCHEMA",
            "RESEARCH_DECOMPOSE_SCHEMA",
        ],
    )
    def test_schema_is_valid_object_type(self, schema: dict) -> None:
        assert isinstance(schema, dict)
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert isinstance(schema["required"], list)
        assert len(schema["required"]) > 0

    def test_classify_schema_has_expected_fields(self) -> None:
        props = RESEARCH_CLASSIFY_SCHEMA["properties"]
        assert "topic" in props
        assert "complexity" in props
        assert "jurisdiction" in props
        assert "key_entities" in props
        assert "search_hints" in props

    def test_classify_schema_topic_enum(self) -> None:
        topic = RESEARCH_CLASSIFY_SCHEMA["properties"]["topic"]
        assert "enum" in topic
        assert "constitutional" in topic["enum"]
        assert "criminal" in topic["enum"]
        assert "civil" in topic["enum"]

    def test_classify_schema_complexity_enum(self) -> None:
        complexity = RESEARCH_CLASSIFY_SCHEMA["properties"]["complexity"]
        assert "enum" in complexity
        assert set(complexity["enum"]) == {"simple", "moderate", "complex"}

    def test_classify_schema_jurisdiction_nullable(self) -> None:
        jurisdiction = RESEARCH_CLASSIFY_SCHEMA["properties"]["jurisdiction"]
        assert jurisdiction.get("nullable") is True

    def test_decompose_schema_has_sub_queries(self) -> None:
        props = RESEARCH_DECOMPOSE_SCHEMA["properties"]
        assert "sub_queries" in props
        items = props["sub_queries"]["items"]
        assert items["type"] == "object"
        assert "query" in items["properties"]
        assert "aspect" in items["properties"]
        assert "rationale" in items["properties"]
        assert set(items["required"]) == {"query", "aspect", "rationale"}
