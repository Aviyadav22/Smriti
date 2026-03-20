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
    # V3 prompts
    ELEMENT_DECOMPOSITION_SYSTEM,
    ELEMENT_DECOMPOSITION_SCHEMA,
    ADVERSARIAL_SEARCH_SYSTEM,
    ADVERSARIAL_SEARCH_SCHEMA,
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
        assert "{evidence}" in RESEARCH_SYNTHESIZE_USER
        assert "{passages}" in RESEARCH_SYNTHESIZE_USER
        assert "{worker_reasoning}" in RESEARCH_SYNTHESIZE_USER
        assert "{communities}" in RESEARCH_SYNTHESIZE_USER
        assert "{strategy_hint}" in RESEARCH_SYNTHESIZE_USER


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
        assert set(complexity["enum"]) == {"simple", "complex", "multi_issue"}

    def test_classify_schema_jurisdiction_nullable(self) -> None:
        jurisdiction = RESEARCH_CLASSIFY_SCHEMA["properties"]["jurisdiction"]
        assert "null" in jurisdiction["type"]

    def test_decompose_schema_has_sub_queries(self) -> None:
        props = RESEARCH_DECOMPOSE_SCHEMA["properties"]
        assert "sub_queries" in props
        items = props["sub_queries"]["items"]
        assert items["type"] == "object"
        assert "query" in items["properties"]
        assert "aspect" in items["properties"]
        assert "rationale" in items["properties"]
        assert set(items["required"]) == {"query", "aspect", "rationale"}


# ---------------------------------------------------------------------------
# Prompt hardening — anti-sycophancy, bench strength, disclaimer
# ---------------------------------------------------------------------------


class TestPromptHardening:
    def test_chat_system_has_anti_sycophancy(self):
        """Chat system prompt must instruct model to flag incorrect assumptions."""
        from app.core.legal.prompts import CHAT_SYSTEM_PROMPT
        assert "incorrect" in CHAT_SYSTEM_PROMPT.lower() or "wrong" in CHAT_SYSTEM_PROMPT.lower()
        assert "flag" in CHAT_SYSTEM_PROMPT.lower() or "correct" in CHAT_SYSTEM_PROMPT.lower()

    def test_chat_system_has_bench_strength(self):
        """Chat system prompt must request bench strength in citations."""
        from app.core.legal.prompts import CHAT_SYSTEM_PROMPT
        assert "bench" in CHAT_SYSTEM_PROMPT.lower()

    def test_chat_system_has_anti_supplementation_rule(self):
        """Chat system prompt must forbid supplementing from training data."""
        from app.core.legal.prompts import CHAT_SYSTEM_PROMPT
        assert "do not supplement" in CHAT_SYSTEM_PROMPT.lower()

    def test_research_synthesize_has_precedent_strength(self):
        """Research synthesis prompt must classify precedent strength."""
        from app.core.legal.prompts import RESEARCH_SYNTHESIZE_SYSTEM
        assert "BINDING" in RESEARCH_SYNTHESIZE_SYSTEM or "binding" in RESEARCH_SYNTHESIZE_SYSTEM.lower()

    def test_case_prep_has_time_bar_check(self):
        """Case prep prompt must flag time-barred arguments."""
        from app.core.legal.prompts import CASE_PREP_PRIORITIZE_SYSTEM
        assert "time-bar" in CASE_PREP_PRIORITIZE_SYSTEM.lower() or "limitation" in CASE_PREP_PRIORITIZE_SYSTEM.lower()


class TestV3Prompts:
    """Tests for Research Agent V3 prompts."""

    def test_element_decomposition_prompt_exists(self) -> None:
        assert isinstance(ELEMENT_DECOMPOSITION_SYSTEM, str)
        assert len(ELEMENT_DECOMPOSITION_SYSTEM) > 100
        assert "decompose" in ELEMENT_DECOMPOSITION_SYSTEM.lower() or \
               "element" in ELEMENT_DECOMPOSITION_SYSTEM.lower()

    def test_element_decomposition_schema_valid(self) -> None:
        assert isinstance(ELEMENT_DECOMPOSITION_SCHEMA, dict)
        assert "elements" in ELEMENT_DECOMPOSITION_SCHEMA["properties"]
        items = ELEMENT_DECOMPOSITION_SCHEMA["properties"]["elements"]["items"]
        assert "element_id" in items["properties"]
        assert "is_contested" in items["properties"]

    def test_adversarial_search_prompt_exists(self) -> None:
        assert isinstance(ADVERSARIAL_SEARCH_SYSTEM, str)
        assert len(ADVERSARIAL_SEARCH_SYSTEM) > 100
        assert "opposing" in ADVERSARIAL_SEARCH_SYSTEM.lower() or \
               "counter" in ADVERSARIAL_SEARCH_SYSTEM.lower()

    def test_adversarial_search_schema_valid(self) -> None:
        assert isinstance(ADVERSARIAL_SEARCH_SCHEMA, dict)
        assert "counter_arguments" in ADVERSARIAL_SEARCH_SCHEMA["properties"]
        items = ADVERSARIAL_SEARCH_SCHEMA["properties"]["counter_arguments"]["items"]
        assert "counter_thesis" in items["properties"]
        assert "target_source" in items["properties"]


class TestV3PromptUpgrades:
    """Tests for V3 prompt upgrades to existing prompts."""

    def test_classify_schema_has_procedural_context(self) -> None:
        props = RESEARCH_CLASSIFY_SCHEMA["properties"]
        assert "procedural_context" in props
        assert "client_position" in props

    def test_evaluate_extract_has_bench_and_obiter(self) -> None:
        from app.core.legal.prompts import RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM
        text = RESEARCH_EVALUATE_AND_EXTRACT_SYSTEM.lower()
        assert "bench" in text
        assert "ratio" in text
        assert "obiter" in text

    def test_merge_has_risk_assessment(self) -> None:
        from app.core.legal.prompts import SPECULATIVE_MERGE_SYSTEM
        assert "risk assessment" in SPECULATIVE_MERGE_SYSTEM.lower()
        assert "counter-argument" in SPECULATIVE_MERGE_SYSTEM.lower()

    def test_quality_check_has_temporal_and_bench(self) -> None:
        from app.core.legal.prompts import LEGAL_QUALITY_CHECK_SYSTEM
        text = LEGAL_QUALITY_CHECK_SYSTEM.lower()
        assert "temporal" in text
        assert "bench" in text
        assert "obiter" in text

    def test_plan_has_element_context(self) -> None:
        from app.core.legal.prompts import RESEARCH_PLAN_SYSTEM
        assert "element" in RESEARCH_PLAN_SYSTEM.lower()
        assert "statute text" in RESEARCH_PLAN_SYSTEM.lower() or "statute" in RESEARCH_PLAN_SYSTEM.lower()
        assert "procedural_context" in RESEARCH_PLAN_SYSTEM


class TestResearchPlanPromptIKFilters:
    """Research plan prompt must mention all IK filter capabilities."""

    def test_has_ik_inline_filters(self):
        from app.core.legal.prompts import RESEARCH_PLAN_SYSTEM
        for keyword in ["title", "cite", "author", "bench", "court_copy"]:
            assert keyword in RESEARCH_PLAN_SYSTEM, f"Missing IK filter: {keyword}"

    def test_has_aggregator_doctypes(self):
        from app.core.legal.prompts import RESEARCH_PLAN_SYSTEM
        for agg in ["highcourts", "tribunals"]:
            assert agg in RESEARCH_PLAN_SYSTEM, f"Missing aggregator: {agg}"

    def test_schema_has_new_filter_properties(self):
        from app.core.legal.prompts import RESEARCH_PLAN_SCHEMA
        filters_props = (
            RESEARCH_PLAN_SCHEMA["properties"]["research_tasks"]["items"]
            ["properties"]["filters"]["properties"]
        )
        for key in ["title", "cite", "author", "bench", "domains"]:
            assert key in filters_props, f"Missing schema filter: {key}"
