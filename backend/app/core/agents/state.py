"""Agent state schemas for LangGraph."""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class ResearchState(TypedDict):
    """State for the Research Agent graph."""
    query: str
    target_court: str
    target_bench: str
    language: str
    sub_queries: list[str]
    search_results: list[dict]
    cross_references: list[dict]
    contradictions: list[dict]
    draft_memo: str
    confidence: float
    messages: Annotated[list[dict], operator.add]
    iteration: int


class CasePrepState(TypedDict):
    """State for the Case Prep Agent graph."""
    document_id: str
    language: str
    analysis: dict
    prioritized_issues: list[dict]
    argument_order: list[dict]
    strategy_points: list[str]
    enhanced_memo: str
    messages: Annotated[list[dict], operator.add]
    iteration: int
    error: str


class StrategyState(TypedDict):
    """State for the Strategy Agent graph."""
    case_facts: str
    target_judge: str          # optional, empty string if not provided
    target_bench: str          # optional, empty string if not provided
    target_court: str          # inferred or explicit
    desired_relief: str
    language: str              # "en" or "hi"
    # Produced by nodes:
    fact_analysis: dict        # parsed facts, parties, causes of action
    judge_profile: dict        # from Judge Analytics (if target_judge set)
    search_results: list[dict]  # hybrid search hits
    precedent_map: list[dict]  # per-argument precedents with strength
    strength_assessment: dict  # {level: "strong"|"moderate"|"weak", reasoning: str, score: float}
    legal_arguments: list[dict]  # ordered arguments with citations
    counter_arguments: list[dict]  # anticipated counters + rebuttals
    judge_considerations: list[dict]  # judge-specific strategic notes
    procedural_suggestions: list[str]
    strategy_memo: str         # final synthesized output
    confidence: float
    messages: Annotated[list[dict], operator.add]
    iteration: int
    error: str


class DraftingState(TypedDict):
    """State for the Drafting Agent graph."""
    doc_type: str            # key into TEMPLATES
    case_facts: str
    language: str            # "en" or "hi"
    relevant_precedents: list[dict]  # user-provided or from prior agent
    additional_context: dict  # type-specific fields (e.g., fir_details for bail)
    target_court: str
    # Produced by nodes:
    template: dict           # resolved DocumentTemplate as dict
    statutory_provisions: list[dict]  # relevant statute sections
    verified_precedents: list[dict]   # citation-verified precedents
    section_drafts: dict     # {section_name: draft_text}
    full_draft: str          # assembled document
    revision_feedback: str   # user feedback for section revision
    export_formats: list[str]  # ["docx", "pdf"]
    messages: Annotated[list[dict], operator.add]
    iteration: int
    error: str
