"""Document analysis service — extracts issues and generates research memos."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.legal.prompts import (
    DOCUMENT_COUNTER_ARGUMENTS_SYSTEM,
    DOCUMENT_COUNTER_ARGUMENTS_USER,
    DOCUMENT_ISSUE_EXTRACTION_SCHEMA,
    DOCUMENT_ISSUE_EXTRACTION_SYSTEM,
    DOCUMENT_ISSUE_EXTRACTION_USER,
    DOCUMENT_RESEARCH_MEMO_SYSTEM,
    DOCUMENT_RESEARCH_MEMO_USER,
)

if TYPE_CHECKING:
    from app.core.interfaces.llm import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class ExtractedIssue:
    """A legal issue extracted from a document."""

    title: str
    description: str


@dataclass
class DocumentExtractionResult:
    """Result of document issue extraction."""

    document_type: str
    issues: list[ExtractedIssue]
    parties: dict[str, str | None]
    key_facts: list[str]
    relief_sought: str | None
    jurisdiction: str | None
    acts_referenced: list[str]


@dataclass
class CounterArgument:
    """A counter-argument with suggested response."""

    issue_title: str
    argument: str
    response: str


class DocumentAnalyzerService:
    """Extracts legal issues from uploaded documents and generates analysis."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def extract_issues(self, document_text: str) -> DocumentExtractionResult:
        """Extract legal issues, parties, facts from document text."""
        max_chars = 100_000
        truncated = document_text[:max_chars]

        prompt = DOCUMENT_ISSUE_EXTRACTION_USER.format(document_text=truncated)

        result = await self._llm.generate_structured(
            prompt,
            system=DOCUMENT_ISSUE_EXTRACTION_SYSTEM,
            output_schema=DOCUMENT_ISSUE_EXTRACTION_SCHEMA,
            temperature=0.1,
        )

        issues = [
            ExtractedIssue(title=i["title"], description=i["description"])
            for i in result.get("issues", [])
        ]

        return DocumentExtractionResult(
            document_type=result.get("document_type", "other"),
            issues=issues,
            parties=result.get("parties", {}),
            key_facts=result.get("key_facts", []),
            relief_sought=result.get("relief_sought"),
            jurisdiction=result.get("jurisdiction"),
            acts_referenced=result.get("acts_referenced", []),
        )

    async def generate_counter_arguments(
        self,
        document_type: str,
        issues_with_precedents: str,
    ) -> list[CounterArgument]:
        """Generate counter-arguments for identified issues."""
        prompt = DOCUMENT_COUNTER_ARGUMENTS_USER.format(
            document_type=document_type,
            issues_with_precedents=issues_with_precedents,
        )

        response = await self._llm.generate(
            prompt,
            system=DOCUMENT_COUNTER_ARGUMENTS_SYSTEM,
            temperature=0.3,
        )

        return self._parse_counter_arguments(response)

    async def generate_research_memo(
        self,
        document_type: str,
        parties: dict[str, str | None],
        relief_sought: str | None,
        key_facts: list[str],
        issues_analysis: str,
        counter_arguments: str,
    ) -> str:
        """Generate a structured research memo."""
        prompt = DOCUMENT_RESEARCH_MEMO_USER.format(
            document_type=document_type,
            parties=json.dumps(parties),
            relief_sought=relief_sought or "Not specified",
            key_facts="\n".join(f"- {f}" for f in key_facts),
            issues_analysis=issues_analysis,
            counter_arguments=counter_arguments,
        )

        return await self._llm.generate(
            prompt,
            system=DOCUMENT_RESEARCH_MEMO_SYSTEM,
            temperature=0.2,
            max_tokens=8192,
        )

    @staticmethod
    def _parse_counter_arguments(response: str) -> list[CounterArgument]:
        """Parse free-form counter-arguments into structured list."""
        arguments: list[CounterArgument] = []
        current_issue = "General"
        lines = response.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("##") or line.lower().startswith("issue"):
                current_issue = line.lstrip("#").strip().rstrip(":")
            elif line.startswith("- **Counter") or line.startswith("**Counter"):
                arg_text = line.split(":**", 1)[-1].strip() if ":**" in line else line
                arguments.append(
                    CounterArgument(
                        issue_title=current_issue,
                        argument=arg_text,
                        response="",
                    )
                )
            elif line.startswith("- **Response") or line.startswith("**Response"):
                resp_text = line.split(":**", 1)[-1].strip() if ":**" in line else line
                if arguments:
                    arguments[-1] = CounterArgument(
                        issue_title=arguments[-1].issue_title,
                        argument=arguments[-1].argument,
                        response=resp_text,
                    )

        return arguments
