"""Agent state schemas for LangGraph."""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class ResearchState(TypedDict):
    """State for the Research Agent graph."""
    query: str
    sub_queries: list[str]
    search_results: Annotated[list[dict], operator.add]
    cross_references: list[dict]
    contradictions: list[dict]
    draft_memo: str
    confidence: float
    messages: list[dict]
    iteration: int


class CasePrepState(TypedDict):
    """State for the Case Prep Agent graph."""
    document_id: str
    analysis: dict
    prioritized_issues: list[dict]
    argument_order: list[dict]
    strategy_points: list[str]
    enhanced_memo: str
    messages: list[dict]
    iteration: int
