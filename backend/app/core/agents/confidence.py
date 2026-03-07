"""Improved confidence scoring for agent research outputs.

Uses a weighted formula considering result relevance (reranker scores),
coverage (cross-reference ratio), source authority (precedent strength),
and contradiction penalty.
"""
from __future__ import annotations

_STRENGTH_SCORES = {
    "BINDING": 1.0,
    "PERSUASIVE": 0.7,
    "DISTINGUISHABLE": 0.4,
    "OVERRULED": 0.1,
}

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
