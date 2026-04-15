"""Agent output quality benchmark tests.

These tests verify that agents produce meaningful, grounded outputs.
Run against a populated database with real LLM access.

Usage:
    pytest tests/quality/test_agent_quality.py -m integration --timeout=120
"""

from __future__ import annotations

import pytest

RESEARCH_SCENARIOS = [
    {
        "query": "What is the current legal position on right to privacy as a fundamental right?",
        "expected_citations": ["Puttaswamy"],
        "expected_sections": ["ratio", "conclusion"],
    },
    {
        "query": "What are the grounds for granting anticipatory bail under Section 438 CrPC?",
        "expected_citations": ["bail"],
        "expected_sections": ["analysis"],
    },
    {
        "query": "How has the Supreme Court interpreted the basic structure doctrine?",
        "expected_citations": ["Kesavananda"],
        "expected_sections": ["ratio"],
    },
    {
        "query": "What is the legal test for determining if a law violates Article 14?",
        "expected_citations": ["Article 14"],
        "expected_sections": ["analysis"],
    },
    {
        "query": "What are the principles governing land acquisition compensation?",
        "expected_citations": ["acquisition"],
        "expected_sections": ["conclusion"],
    },
]

STRATEGY_SCENARIOS = [
    {
        "case_facts": "Client was arrested under Section 420 IPC for alleged fraud in a real estate transaction. No prior criminal record. Cooperated with investigation.",
        "desired_relief": "Regular bail",
        "expected_in_memo": ["bail", "fraud", "cooperation"],
    },
    {
        "case_facts": "Government acquired 5 acres of agricultural land for highway construction. Compensation offered at Rs 500/sq ft, market rate is Rs 2000/sq ft.",
        "desired_relief": "Enhanced compensation",
        "expected_in_memo": ["compensation", "market value", "acquisition"],
    },
    {
        "case_facts": "Employee terminated without notice after 15 years of service. No disciplinary proceedings conducted. Employer claims restructuring.",
        "desired_relief": "Reinstatement with back wages",
        "expected_in_memo": ["termination", "natural justice", "reinstatement"],
    },
]

DRAFTING_SCENARIOS = [
    {
        "doc_type": "bail_application",
        "case_facts": "Accused in custody for 60 days under Section 302 IPC. Circumstantial evidence only. No flight risk.",
        "expected_sections": ["prayer", "grounds"],
    },
    {
        "doc_type": "writ_petition_226",
        "case_facts": "Municipal corporation demolished shop without notice. Violation of natural justice principles.",
        "expected_sections": ["prayer", "grounds"],
    },
    {
        "doc_type": "legal_notice",
        "case_facts": "Tenant has not paid rent for 6 months despite repeated reminders. Monthly rent Rs 25,000.",
        "expected_sections": ["notice", "demand"],
    },
]


@pytest.mark.integration
class TestResearchAgentQuality:
    """Verify Research Agent produces grounded, cited memos."""

    @pytest.mark.parametrize("scenario", RESEARCH_SCENARIOS)
    async def test_research_memo_has_citations(self, scenario: dict, agent_runner) -> None:
        """Research memo should contain expected citations."""
        result = await agent_runner.run_research(scenario["query"])
        memo = result.get("research_memo", "").lower()

        assert len(memo) > 100, "Research memo is too short"

        for citation in scenario["expected_citations"]:
            assert (
                citation.lower() in memo
            ), f"Expected '{citation}' in research memo for: {scenario['query']}"

    @pytest.mark.parametrize("scenario", RESEARCH_SCENARIOS)
    async def test_research_has_confidence(self, scenario: dict, agent_runner) -> None:
        """Research result should include a confidence score."""
        result = await agent_runner.run_research(scenario["query"])
        confidence = result.get("confidence", 0)
        assert 0 < confidence <= 1, f"Confidence {confidence} out of range"


@pytest.mark.integration
class TestStrategyAgentQuality:
    """Verify Strategy Agent produces actionable strategy memos."""

    @pytest.mark.parametrize("scenario", STRATEGY_SCENARIOS)
    async def test_strategy_memo_content(self, scenario: dict, agent_runner) -> None:
        """Strategy memo should address case facts and relief sought."""
        result = await agent_runner.run_strategy(
            case_facts=scenario["case_facts"],
            desired_relief=scenario["desired_relief"],
        )
        memo = result.get("strategy_memo", "").lower()

        assert len(memo) > 200, "Strategy memo is too short"

        for term in scenario["expected_in_memo"]:
            assert term.lower() in memo, f"Expected '{term}' in strategy memo"

    @pytest.mark.parametrize("scenario", STRATEGY_SCENARIOS)
    async def test_strategy_has_strength_assessment(self, scenario: dict, agent_runner) -> None:
        """Strategy result should include case strength assessment."""
        result = await agent_runner.run_strategy(
            case_facts=scenario["case_facts"],
            desired_relief=scenario["desired_relief"],
        )
        strength = result.get("strength_assessment", "")
        assert strength in ("strong", "moderate", "weak"), f"Unexpected strength: {strength}"


@pytest.mark.integration
class TestDraftingAgentQuality:
    """Verify Drafting Agent generates valid legal documents."""

    @pytest.mark.parametrize("scenario", DRAFTING_SCENARIOS)
    async def test_draft_has_sections(self, scenario: dict, agent_runner) -> None:
        """Draft should contain expected document sections."""
        result = await agent_runner.run_drafting(
            doc_type=scenario["doc_type"],
            case_facts=scenario["case_facts"],
        )
        draft = result.get("full_draft", "").lower()

        assert len(draft) > 300, "Draft document is too short"

        for section in scenario["expected_sections"]:
            assert (
                section.lower() in draft
            ), f"Expected section '{section}' in {scenario['doc_type']} draft"

    @pytest.mark.parametrize("scenario", DRAFTING_SCENARIOS)
    async def test_draft_has_no_placeholder(self, scenario: dict, agent_runner) -> None:
        """Draft should not contain unfilled placeholders."""
        result = await agent_runner.run_drafting(
            doc_type=scenario["doc_type"],
            case_facts=scenario["case_facts"],
        )
        draft = result.get("full_draft", "")

        # Check for common placeholder patterns
        for placeholder in ["[INSERT", "[TODO", "[PLACEHOLDER", "{{", "}}"]:
            assert placeholder not in draft, f"Found placeholder '{placeholder}' in draft"
