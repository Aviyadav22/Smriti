"""Tests for DocumentAnalyzerService."""

from unittest.mock import AsyncMock

import pytest

from app.core.analysis.document_analyzer import (
    DocumentAnalyzerService,
    DocumentExtractionResult,
)


def _make_mock_llm() -> AsyncMock:
    return AsyncMock()


class TestExtractIssues:
    @pytest.mark.asyncio
    async def test_extracts_issues_from_document(self) -> None:
        llm = _make_mock_llm()
        llm.generate_structured.return_value = {
            "document_type": "petition",
            "issues": [
                {
                    "title": "Right to Privacy",
                    "description": "Whether surveillance violates Article 21",
                },
                {"title": "State Power", "description": "Scope of state surveillance authority"},
            ],
            "parties": {"petitioner": "John Doe", "respondent": "State of Maharashtra"},
            "key_facts": ["Petitioner's phone was tapped", "No warrant obtained"],
            "relief_sought": "Quash the surveillance order",
            "jurisdiction": "constitutional",
            "acts_referenced": ["Indian Telegraph Act, 1885"],
        }

        service = DocumentAnalyzerService(llm)
        result = await service.extract_issues("Sample legal document text...")

        assert isinstance(result, DocumentExtractionResult)
        assert result.document_type == "petition"
        assert len(result.issues) == 2
        assert result.issues[0].title == "Right to Privacy"
        assert result.parties["petitioner"] == "John Doe"
        assert len(result.key_facts) == 2
        assert result.relief_sought == "Quash the surveillance order"

    @pytest.mark.asyncio
    async def test_handles_empty_issues(self) -> None:
        llm = _make_mock_llm()
        llm.generate_structured.return_value = {
            "document_type": "other",
            "issues": [],
            "parties": {},
            "key_facts": [],
            "relief_sought": None,
            "jurisdiction": None,
            "acts_referenced": [],
        }

        service = DocumentAnalyzerService(llm)
        result = await service.extract_issues("Short text")
        assert result.issues == []

    @pytest.mark.asyncio
    async def test_truncates_long_documents(self) -> None:
        llm = _make_mock_llm()
        llm.generate_structured.return_value = {
            "document_type": "brief",
            "issues": [],
            "parties": {},
            "key_facts": [],
            "relief_sought": None,
            "jurisdiction": None,
            "acts_referenced": [],
        }

        service = DocumentAnalyzerService(llm)
        long_text = "x" * 200_000
        await service.extract_issues(long_text)

        call_args = llm.generate_structured.call_args
        prompt = call_args.args[0]
        assert len(prompt) < 200_000


class TestGenerateResearchMemo:
    @pytest.mark.asyncio
    async def test_generates_memo(self) -> None:
        llm = _make_mock_llm()
        llm.generate.return_value = "# Research Memo\n\n## Executive Summary\nThis memo..."

        service = DocumentAnalyzerService(llm)
        memo = await service.generate_research_memo(
            document_type="petition",
            parties={"petitioner": "A", "respondent": "B"},
            relief_sought="Damages",
            key_facts=["Fact 1", "Fact 2"],
            issues_analysis="Issue 1: ...",
            counter_arguments="Counter 1: ...",
        )

        assert "Research Memo" in memo
        assert llm.generate.called


class TestParseCounterArguments:
    def test_parses_formatted_counter_arguments(self) -> None:
        response = """\
## Issue: Right to Privacy

- **Counter-Argument:** State has power under Article 19(2)
- **Response:** Article 19(2) restrictions must be reasonable

## Issue: Due Process

- **Counter-Argument:** No fundamental right to prior notice
- **Response:** Natural justice principles require hearing
"""
        result = DocumentAnalyzerService._parse_counter_arguments(response)
        assert len(result) == 2
        assert result[0].issue_title == "Issue: Right to Privacy"
        assert "Article 19(2)" in result[0].argument
        assert "reasonable" in result[0].response

    def test_handles_empty_response(self) -> None:
        result = DocumentAnalyzerService._parse_counter_arguments("")
        assert result == []
