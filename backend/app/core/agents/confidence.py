"""Improved confidence scoring for agent research outputs.

Uses a weighted formula considering result relevance (reranker scores),
coverage (cross-reference ratio), source authority (precedent strength),
and contradiction penalty.
"""
from __future__ import annotations

from typing import TypedDict

_STRENGTH_SCORES = {
    "BINDING": 1.0,
    "PERSUASIVE": 0.7,
    "DISTINGUISHABLE": 0.4,
    "OVERRULED": 0.1,
}


class ConfidenceBreakdown(TypedDict):
    """Decomposed confidence components for agent introspection."""

    overall: float
    data_confidence: float
    legal_confidence: float
    consistency_confidence: float

# Component weights (must sum to 1.0)
_W_RELEVANCE = 0.40
_W_COVERAGE = 0.20
_W_AUTHORITY = 0.20
_W_CONTRADICTION = 0.20


def calculate_confidence(
    reranker_scores: list[float],
    cross_ref_ratio: float,
    precedent_strengths: list[str],
    contradiction_count: int,
    total_results: int,
) -> float:
    """Calculate a quality-weighted confidence score.

    Args:
        reranker_scores: Top-N reranker scores (0-1). Use top 5 at most.
        cross_ref_ratio: Fraction of sub-queries with overlapping results (0-1).
        precedent_strengths: List of strength labels for cited precedents.
        contradiction_count: Number of contradictions found.
        total_results: Total search results found.

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    if total_results == 0:
        return 0.0

    # 1. Result relevance -- mean of top reranker scores
    top_scores = reranker_scores[:5]
    relevance = sum(top_scores) / len(top_scores) if top_scores else 0.0

    # 2. Coverage -- cross-reference ratio (already 0-1)
    coverage = min(cross_ref_ratio, 1.0)

    # 3. Source authority -- mean precedent strength score
    if precedent_strengths:
        strength_values = [
            _STRENGTH_SCORES.get(s, 0.5) for s in precedent_strengths
        ]
        authority = sum(strength_values) / len(strength_values)
    else:
        authority = 0.3  # unknown = low-ish

    # 4. Contradiction penalty -- more contradictions = lower confidence
    if total_results > 0 and contradiction_count > 0:
        contradiction_ratio = contradiction_count / total_results
        contradiction_factor = max(0.0, 1.0 - contradiction_ratio)
    else:
        contradiction_factor = 1.0

    confidence = (
        _W_RELEVANCE * relevance
        + _W_COVERAGE * coverage
        + _W_AUTHORITY * authority
        + _W_CONTRADICTION * contradiction_factor
    )

    return min(1.0, max(0.0, confidence))


def calculate_confidence_detailed(
    reranker_scores: list[float],
    cross_ref_ratio: float,
    precedent_strengths: list[str],
    contradiction_count: int,
    total_results: int,
    effective_strengths: list[float] | None = None,
) -> ConfidenceBreakdown:
    """Calculate confidence with a full sub-component decomposition.

    This is an extended version of :func:`calculate_confidence` that returns
    a :class:`ConfidenceBreakdown` dict so agents can inspect *why* the
    confidence is high or low.

    Args:
        reranker_scores: Top-N reranker scores (0-1).
        cross_ref_ratio: Fraction of sub-queries with overlapping results (0-1).
        precedent_strengths: List of strength labels for cited precedents.
        contradiction_count: Number of contradictions found.
        total_results: Total search results found.
        effective_strengths: Optional pre-computed effective strength floats
            (from :func:`~app.core.legal.precedent_strength.compute_effective_strength`).
            When provided these take priority over *precedent_strengths* for the
            legal confidence component.

    Returns:
        A :class:`ConfidenceBreakdown` dict with ``overall``,
        ``data_confidence``, ``legal_confidence``, and
        ``consistency_confidence`` keys.
    """
    if total_results == 0:
        return ConfidenceBreakdown(
            overall=0.0,
            data_confidence=0.0,
            legal_confidence=0.0,
            consistency_confidence=0.0,
        )

    # --- data_confidence (relevance + coverage) ---
    top_scores = reranker_scores[:5]
    relevance = sum(top_scores) / len(top_scores) if top_scores else 0.0
    coverage = min(cross_ref_ratio, 1.0)
    data_confidence = (relevance + coverage) / 2.0

    # --- legal_confidence (authority from precedent/effective strengths) ---
    if effective_strengths:
        legal_confidence = sum(effective_strengths) / len(effective_strengths)
    elif precedent_strengths:
        strength_values = [
            _STRENGTH_SCORES.get(s, 0.5) for s in precedent_strengths
        ]
        legal_confidence = sum(strength_values) / len(strength_values)
    else:
        legal_confidence = 0.3

    # --- consistency_confidence ---
    if total_results > 0 and contradiction_count > 0:
        contradiction_ratio = contradiction_count / total_results
        consistency_confidence = max(0.0, 1.0 - contradiction_ratio)
    else:
        consistency_confidence = 1.0

    # Overall uses same weights as calculate_confidence
    overall = (
        (_W_RELEVANCE + _W_COVERAGE) * data_confidence
        + _W_AUTHORITY * legal_confidence
        + _W_CONTRADICTION * consistency_confidence
    )
    overall = min(1.0, max(0.0, overall))

    return ConfidenceBreakdown(
        overall=overall,
        data_confidence=min(1.0, max(0.0, data_confidence)),
        legal_confidence=min(1.0, max(0.0, legal_confidence)),
        consistency_confidence=min(1.0, max(0.0, consistency_confidence)),
    )
